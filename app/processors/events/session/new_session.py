from scalecodec.base import ScaleBytes
from scalecodec.exceptions import RemainingScaleBytesNotEmptyException
from substrateinterface import SubstrateInterface

from app import settings, utils
from app.models.data import Session, SessionValidator, SessionTotal, Account, SessionNominator, RuntimeStorage, \
    ValidatorAuditFromChain
from app.processors.base import EventProcessor
from app.settings import LEGACY_SESSION_VALIDATOR_LOOKUP, SUBSTRATE_METADATA_VERSION, SUBSTRATE_ADDRESS_TYPE
from app.utils.ss58 import ss58_encode


class NewSessionEventProcessor(EventProcessor):
    module_id = 'Session'
    event_id = 'NewSession'

    def add_session(self, db_session, session_id):
        nominators = []

        substrate: SubstrateInterface = self.substrate
        if self.substrate.metadata_decoder is None:
            self.substrate.metadata_decoder = substrate.get_block_metadata(self.block.hash)

        # Retrieve current era
        try:
            current_era = utils.query_storage(pallet_name="Staking", storage_name="CurrentEra", substrate=substrate,
                                              block_hash=self.block.hash).value
        except Exception as e:
            print("query current_era storage error:{}".format(e))
            current_era = None

        # Retrieve validators for new session from storage
        try:
            validators = utils.query_storage(pallet_name="Session", storage_name="Validators", substrate=substrate,
                                             block_hash=self.block.hash).value or []
        except Exception as e:
            print("query validators storage error:{}".format(e))
            validators = []

        for rank_nr, validator_account in enumerate(validators):
            validator_ledger = {}
            validator_session = None

            # GenericAccountId
            validator_stash = validator_account.replace('0x', '')

            # Retrieve controller account
            try:
                validator_controller = utils.query_storage(pallet_name="Staking", storage_name="Bonded",
                                                           substrate=substrate,
                                                           block_hash=self.block.hash, params=[validator_account]).value
                if validator_controller:
                    validator_controller = validator_controller.replace('0x', '')
            except Exception as e:
                print("query validator_controller storage error:{}".format(e))
                validator_controller = None

            # Retrieve validator preferences for stash account
            try:
                staking_eras_validator_prefs = utils.query_storage(pallet_name="Staking", storage_name="ErasValidatorPrefs",
                                                      substrate=substrate,
                                                      block_hash=self.block.hash,
                                                      params=[current_era, validator_account])
                # print("%%%%%%%%% staking_eras_validator_prefs = ", staking_eras_validator_prefs, [current_era, validator_account])
                validator_prefs = staking_eras_validator_prefs.value
            except Exception as e:
                print("query validator_prefs storage error:{}, but not very important".format(e))
                validator_prefs = None

            if not validator_prefs:
                validator_prefs = {'commission': None}

            # Retrieve bonded
            try:
                exposure = utils.query_storage(pallet_name="Staking", storage_name="ErasStakers",
                                               substrate=substrate,
                                               block_hash=self.block.hash,
                                               params=[current_era, validator_account]).value
            except Exception as e:
                print("query exposure storage error:{}".format(e))
                exposure = None

            if not exposure:
                exposure = {}

            if exposure.get('total'):
                bonded_nominators = exposure.get('total') - exposure.get('own')
            else:
                bonded_nominators = None

            # Remove old data before insert
            for item in SessionValidator.query(db_session).filter_by(
                    session_id=session_id, rank_validator=rank_nr):
                db_session.delete(item)

            session_validator = SessionValidator(
                session_id=session_id,
                validator_controller=validator_controller,
                validator_stash=validator_stash,
                bonded_total=exposure.get('total'),
                bonded_active=validator_ledger.get('active'),
                bonded_own=exposure.get('own'),
                bonded_nominators=bonded_nominators,
                validator_session=validator_session,
                rank_validator=rank_nr,
                unlocking=validator_ledger.get('unlocking'),
                count_nominators=len(exposure.get('others', [])),
                unstake_threshold=None,
                commission=validator_prefs.get('commission')
            )

            session_validator.save(db_session)

            # Store nominators
            for rank_nominator, nominator_info in enumerate(exposure.get('others', [])):
                nominator_stash = nominator_info.get('who').replace('0x', '')
                nominators.append(nominator_stash)

                session_nominator = SessionNominator(
                    session_id=session_id,
                    rank_validator=rank_nr,
                    rank_nominator=rank_nominator,
                    nominator_stash=nominator_stash,
                    bonded=nominator_info.get('value'),
                )

                session_nominator.save(db_session)


        # Store session
        session = Session(
            id=session_id,
            start_at_block=self.block.id + 1,
            created_at_block=self.block.id,
            created_at_extrinsic=self.event.extrinsic_idx,
            created_at_event=self.event.event_idx,
            count_validators=len(validators),
            count_nominators=len(set(nominators)),
            era=current_era
        )

        exists_session_data = Session.query(db_session).filter_by(id=session.id).first()
        if exists_session_data:
            db_session.delete(exists_session_data)

        session.save(db_session)

        # Retrieve previous session to calculate count_blocks
        prev_session = Session.query(db_session).filter_by(id=session_id - 1).first()

        if prev_session:
            count_blocks = self.block.id - prev_session.start_at_block + 1
        else:
            count_blocks = self.block.id

        session_total = SessionTotal(
            id=session_id - 1,
            end_at_block=self.block.id,
            count_blocks=count_blocks
        )

        exists_session_total_data = SessionTotal.query(db_session).filter_by(id=session_total.id).first()
        if exists_session_total_data:
            # If exists delete first
            db_session.delete(exists_session_total_data)

        session_total.save(db_session)

        # Update validator flags
        validator_ids = [v.replace('0x', '') for v in validators]

        Account.query(db_session).filter(
            Account.id.in_(validator_ids), Account.was_validator == False
        ).update({Account.was_validator: True}, synchronize_session='fetch')

        Account.query(db_session).filter(
            Account.id.notin_(validator_ids), Account.is_validator == True
        ).update({Account.is_validator: False}, synchronize_session='fetch')

        Account.query(db_session).filter(
            Account.id.in_(validator_ids), Account.is_validator == False
        ).update({Account.is_validator: True}, synchronize_session='fetch')

        # Update nominator flags
        Account.query(db_session).filter(
            Account.id.in_(nominators), Account.was_nominator == False
        ).update({Account.was_nominator: True}, synchronize_session='fetch')

        Account.query(db_session).filter(
            Account.id.notin_(nominators), Account.is_nominator == True
        ).update({Account.is_nominator: False}, synchronize_session='fetch')

        Account.query(db_session).filter(
            Account.id.in_(nominators), Account.is_nominator == False
        ).update({Account.is_nominator: True}, synchronize_session='fetch')

    # for old version
    def add_session_old(self, db_session, session_id):
        """
            new_version use add_session instead of
        """
        current_era = None
        validators = []
        nominators = []
        validation_session_lookup = {}

        substrate = self.substrate
        # Retrieve current era
        storage_call = RuntimeStorage.query(db_session).filter_by(
            module_id='Staking',
            name='CurrentEra',
            spec_version=self.block.spec_version_id
        ).first()

        def query_storage_value(storage_obj: RuntimeStorage, block_hash, params: list = None):
            if params is None:
                params = []
            storage_hash = substrate.generate_storage_hash(
                storage_module=storage_obj.module_id,
                storage_function=storage_obj.name,
                params=params,
                hashers=storage_obj.get_hashers()
            )
            return substrate.get_storage_by_key(block_hash, storage_hash)

        if storage_call:
            try:
                query_value = query_storage_value(storage_call, self.block.hash)
                scale_class = substrate.runtime_config.create_scale_object(storage_call.type_value,
                                                                           data=ScaleBytes(query_value))
                current_era = scale_class.decode()
            except Exception as e:
                print("parse type:{} error:{}".format(storage_call.type_value, e))
                pass

        # Retrieve validators for new session from storage

        storage_call = RuntimeStorage.query(db_session).filter_by(
            module_id='Session',
            name='Validators',
            spec_version=self.block.spec_version_id
        ).first()

        if storage_call:
            try:
                query_value = query_storage_value(storage_call, self.block.hash)
                scale_class = substrate.runtime_config.create_scale_object(storage_call.type_value,
                                                                           data=ScaleBytes(query_value))
                validators = scale_class.decode() or []
            except Exception as e:
                print("parse type:{} error:{}".format(storage_call.type_value, e))
                pass

        # Retrieve all sessions in one call
        if not LEGACY_SESSION_VALIDATOR_LOOKUP:

            # Retrieve session account
            # TODO move to network specific data types
            storage_call = RuntimeStorage.query(db_session).filter_by(
                module_id='Session',
                name='QueuedKeys',
                spec_version=self.block.spec_version_id
            ).first()

            if storage_call:

                try:
                    query_value = query_storage_value(storage_call, self.block.hash)
                    scale_class = substrate.runtime_config.create_scale_object(storage_call.type_value,
                                                                               data=ScaleBytes(query_value))
                    validator_session_list = scale_class.decode() or []
                except Exception as e:
                    print("parse type:{} error:{}".format(storage_call.type_value, e))
                    validator_session_list = []

                # build lookup dict
                validation_session_lookup = {}
                for validator_session_item in validator_session_list:
                    validation_session_lookup[validator_session_item[0].replace('0x', '')] = validator_session_item[1]

        for rank_nr, validator_account in enumerate(validators):
            validator_stash = None
            validator_controller = None
            validator_ledger = {}
            validator_prefs = {}
            validator_session = ''
            exposure = {}

            if not LEGACY_SESSION_VALIDATOR_LOOKUP:
                validator_stash = validator_account.replace('0x', '')

                # Retrieve stash account
                storage_call = RuntimeStorage.query(db_session).filter_by(
                    module_id='Staking',
                    name='Bonded',
                    spec_version=self.block.spec_version_id
                ).first()

                if storage_call:
                    try:
                        query_value = query_storage_value(storage_call, self.block.hash, [validator_stash])
                        scale_class = substrate.runtime_config.create_scale_object(storage_call.type_value,
                                                                                   data=ScaleBytes(query_value))
                        validator_controller = scale_class.decode() or ''
                        validator_controller = validator_controller.replace('0x', '')

                    except RemainingScaleBytesNotEmptyException:
                        print("parse type:{} error:{}".format(storage_call.type_value, e))
                        pass

                # Retrieve session account
                validator_session = validation_session_lookup.get(validator_stash)

            else:
                validator_controller = validator_account.replace('0x', '')

                # Retrieve stash account
                storage_call = RuntimeStorage.query(db_session).filter_by(
                    module_id='staking',
                    name='Ledger',
                    spec_version=self.block.spec_version_id
                ).first()

                if storage_call:
                    try:
                        validator_ledger = substrate.get_storage(
                            block_hash=self.block.hash,
                            module="Staking",
                            function="Ledger",
                            params=[validator_controller],
                            return_scale_type=storage_call.get_return_type(),
                            hasher=storage_call.type_hasher,
                            metadata_version=SUBSTRATE_METADATA_VERSION
                        ) or {}

                        validator_stash = validator_ledger.get('stash', '').replace('0x', '')

                    except RemainingScaleBytesNotEmptyException:
                        pass

                # Retrieve session account
                storage_call = RuntimeStorage.query(db_session).filter_by(
                    module_id='session',
                    name='NextKeyFor',
                    spec_version=self.block.spec_version_id
                ).first()

                if storage_call:
                    try:
                        validator_session = substrate.get_storage(
                            block_hash=self.block.hash,
                            module="Session",
                            function="NextKey",
                            params=[validator_controller],
                            return_scale_type=storage_call.get_return_type(),
                            hasher=storage_call.type_hasher,
                            metadata_version=SUBSTRATE_METADATA_VERSION
                        ) or ''
                    except RemainingScaleBytesNotEmptyException:
                        pass

                    validator_session = validator_session.replace('0x', '')

            # Retrieve validator preferences for stash account
            storage_call = RuntimeStorage.query(db_session).filter_by(
                module_id='Staking',
                name='Validators',
                spec_version=self.block.spec_version_id
            ).first()

            if storage_call:
                try:
                    query_value = query_storage_value(storage_call, self.block.hash, [validator_stash])
                    scale_class = substrate.runtime_config.create_scale_object(storage_call.type_value,
                                                                               data=ScaleBytes(query_value))
                    validator_prefs = scale_class.decode() or {}
                except RemainingScaleBytesNotEmptyException:
                    print("parse type:{} error:{}".format(storage_call.type_value, e))
                    pass

            # Retrieve nominators
            storage_call = RuntimeStorage.query(db_session).filter_by(
                module_id='Staking',
                name='Nominators',
                spec_version=self.block.spec_version_id
            ).first()

            if storage_call:
                try:
                    query_value = query_storage_value(storage_call, self.block.hash, [validator_stash])
                    exposure = {}
                    if query_value is not None:
                        scale_class = substrate.runtime_config.create_scale_object(storage_call.type_value,
                                                                                   data=ScaleBytes(query_value))
                        exposure = scale_class.decode() or {}
                except RemainingScaleBytesNotEmptyException:
                    print("parse type:{} error:{}".format(storage_call.type_value, e))
                    pass

            if exposure.get('total'):
                bonded_nominators = exposure.get('total') - exposure.get('own')
            else:
                bonded_nominators = None

            session_validator = SessionValidator(
                session_id=session_id,
                validator_controller=validator_controller,
                validator_stash=validator_stash,
                bonded_total=exposure.get('total'),
                bonded_active=validator_ledger.get('active'),
                bonded_own=exposure.get('own'),
                bonded_nominators=bonded_nominators,
                validator_session=validator_session,
                rank_validator=rank_nr,
                unlocking=validator_ledger.get('unlocking'),
                count_nominators=len(exposure.get('others', [])),
                unstake_threshold=validator_prefs.get('unstakeThreshold'),
                commission=validator_prefs.get('commission')
            )

            session_validator.save(db_session)

            # Store nominators
            for rank_nominator, nominator_info in enumerate(exposure.get('others', [])):
                nominator_stash = nominator_info.get('who').replace('0x', '')
                nominators.append(nominator_stash)

                session_nominator = SessionNominator(
                    session_id=session_id,
                    rank_validator=rank_nr,
                    rank_nominator=rank_nominator,
                    nominator_stash=nominator_stash,
                    bonded=nominator_info.get('value'),
                )

                session_nominator.save(db_session)

        # Store session
        session = Session(
            id=session_id,
            start_at_block=self.block.id + 1,
            created_at_block=self.block.id,
            created_at_extrinsic=self.event.extrinsic_idx,
            created_at_event=self.event.event_idx,
            count_validators=len(validators),
            count_nominators=len(set(nominators)),
            era=current_era
        )

        exists_session_data = Session.query(db_session).filter_by(id=session.id).first()
        if exists_session_data:
            session.delete(exists_session_data)

        session.save(db_session)

        # Retrieve previous session to calculate count_blocks
        prev_session = Session.query(db_session).filter_by(id=session_id - 1).first()

        if prev_session:
            count_blocks = self.block.id - prev_session.start_at_block + 1
        else:
            count_blocks = self.block.id

        session_total = SessionTotal(
            id=session_id - 1,
            end_at_block=self.block.id,
            count_blocks=count_blocks
        )

        exists_session_total_data = SessionTotal.query(db_session).filter_by(id=session_total.id).first()
        if exists_session_total_data:
            # If exists delete first
            db_session.delete(exists_session_total_data)

        session_total.save(db_session)

        # Update validator flags
        validator_ids = [v.replace('0x', '') for v in validators]

        Account.query(db_session).filter(
            Account.id.in_(validator_ids), Account.was_validator == False
        ).update({Account.was_validator: True}, synchronize_session='fetch')

        Account.query(db_session).filter(
            Account.id.notin_(validator_ids), Account.is_validator == True
        ).update({Account.is_validator: False}, synchronize_session='fetch')

        Account.query(db_session).filter(
            Account.id.in_(validator_ids), Account.is_validator == False
        ).update({Account.is_validator: True}, synchronize_session='fetch')

        # Update nominator flags
        Account.query(db_session).filter(
            Account.id.in_(nominators), Account.was_nominator == False
        ).update({Account.was_nominator: True}, synchronize_session='fetch')

        Account.query(db_session).filter(
            Account.id.notin_(nominators), Account.is_nominator == True
        ).update({Account.is_nominator: False}, synchronize_session='fetch')

        Account.query(db_session).filter(
            Account.id.in_(nominators), Account.is_nominator == False
        ).update({Account.is_nominator: True}, synchronize_session='fetch')

    def accumulation_hook(self, db_session):
        self.block.count_sessions_new += 1

        substrate = self.substrate
        # Update ValidatorAuditFromChain

        # block_hash = substrate.get_chain_finalised_head()
        # substrate.init_runtime(block_hash=block_hash)

        print('################### KAMI #####', self.block.hash)
        # aresOracle.finalPerCheckResult
        # all_final_results = utils.query_storage(pallet_name="AresOracle", storage_name="FinalPerCheckResult",
        #                                         substrate=substrate,
        #                                         block_hash=self.block.hash)
        all_final_results = utils.query_all_storage(pallet_name="AresOracle", storage_name="FinalPerCheckResult",
                                                substrate=substrate, block_hash=self.block.hash)
        # // aresOracle.confPreCheckTokenList
        # pre_check_token_list = utils.query_storage(pallet_name="AresOracle", storage_name="ConfPreCheckTokenList",
        #                                            substrate=substrate, block_hash=self.block.hash)
        # current_era = utils.query_storage(pallet_name="Staking", storage_name="CurrentEra", substrate=substrate,
        #                                   block_hash=self.block.hash).value
        # print(all_final_results, pre_check_token_list, current_era)

        if (all_final_results):
            for key in all_final_results:
                print('###################### KAMI - ', key)
                task_result = all_final_results[key].value
                task_validator = ss58_encode(key.replace('0x', ''), SUBSTRATE_ADDRESS_TYPE)
                task_ares_authority = task_result[3]
                task_block_number = task_result[0]
                task_status = task_result[1]

                # ValidatorAuditFromChain
                validatorAudit: ValidatorAuditFromChain = ValidatorAuditFromChain.query(db_session).filter_by(
                    validator=task_validator,
                    ares_authority=task_ares_authority,
                ).first()
                if validatorAudit:
                    # update.
                    validatorAudit.block_number = task_block_number
                    validatorAudit.status = task_status
                    validatorAudit.save(db_session)
                else:
                    # insert.
                    validatorAudit = ValidatorAuditFromChain(
                        validator=task_validator,
                        ares_authority=task_ares_authority,
                        block_number=task_block_number,
                        status=task_status,
                    )
                    validatorAudit.save(db_session)

    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):
        session_id = self.event.attributes[0]['value']

        if settings.get_versioned_setting('NEW_SESSION_EVENT_HANDLER', self.block.spec_version_id):
            self.add_session(db_session, session_id)
        else:
            self.add_session_old(db_session, session_id)

    def process_search_index(self, db_session):
        try:
            validators = utils.query_storage(pallet_name="Session", storage_name="Validators", substrate=self.substrate,
                                             block_hash=self.block.hash).value
            # Add search indices for validators sessions
            for account_id in validators:
                search_index = self.add_search_index(
                    index_type_id=settings.SEARCH_INDEX_STAKING_SESSION,
                    account_id=account_id.replace('0x', '')
                )

                search_index.save(db_session)
        except ValueError:
            pass
