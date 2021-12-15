#  Polkascan PRE Harvester
#
#  Copyright 2018-2019 openAware BV (NL).
#  This file is part of Polkascan.
#
#  Polkascan is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Polkascan is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Polkascan. If not, see <http://www.gnu.org/licenses/>.
#
#  event.py
#
from packaging import version
from scalecodec.base import RuntimeConfiguration, ScaleBytes
from scalecodec.types import GenericStorageEntryMetadata, ss58_decode
from app import settings, utils
from app.models.data import Contract, Session, AccountAudit, \
    AccountIndexAudit, SessionTotal, SessionValidator, RuntimeStorage, \
    SessionNominator, IdentityAudit, IdentityJudgementAudit, Account
from app.processors.base import EventProcessor
from app.settings import ACCOUNT_AUDIT_TYPE_NEW, ACCOUNT_AUDIT_TYPE_REAPED, ACCOUNT_INDEX_AUDIT_TYPE_NEW, \
    ACCOUNT_INDEX_AUDIT_TYPE_REAPED, LEGACY_SESSION_VALIDATOR_LOOKUP, SEARCH_INDEX_SLASHED_ACCOUNT, \
    SEARCH_INDEX_BALANCETRANSFER, SEARCH_INDEX_HEARTBEATRECEIVED, SUBSTRATE_METADATA_VERSION, \
    IDENTITY_TYPE_SET, IDENTITY_TYPE_CLEARED, IDENTITY_TYPE_KILLED, \
    IDENTITY_JUDGEMENT_TYPE_GIVEN

from scalecodec.exceptions import RemainingScaleBytesNotEmptyException
from substrateinterface import SubstrateInterface
from substrateinterface.exceptions import StorageFunctionNotFound
import logging


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
                validator_prefs = utils.query_storage(pallet_name="Staking", storage_name="ErasValidatorPrefs",
                                                      substrate=substrate,
                                                      block_hash=self.block.hash,
                                                      params=[current_era, validator_account]).value
            except Exception as e:
                print("query validator_prefs storage error:{}".format(e))
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
                            function="NextKeyFor",
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


class NewAccountEventProcessor(EventProcessor):
    module_id = 'Balances'
    event_id = 'NewAccount'

    def accumulation_hook(self, db_session):
        print("new_balance")
        # Check event requirements
        if len(self.event.attributes) == 2 and \
                self.event.attributes[0]['type'] == 'AccountId' and self.event.attributes[1]['type'] == 'Balance':
            account_id = self.event.attributes[0].replace('0x', '')
            balance = self.event.attributes[1]

            self.block._accounts_new.append(account_id)

            account_audit = AccountAudit(
                account_id=account_id,
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=ACCOUNT_AUDIT_TYPE_NEW
            )

            account_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in AccountAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_ACCOUNT_CREATED,
            account_id=self.event.attributes[0].replace('0x', '')
        )

        search_index.save(db_session)


class SystemNewAccountEventProcessor(EventProcessor):
    module_id = 'System'
    event_id = 'NewAccount'

    def accumulation_hook(self, db_session):
        print("new Account")
        # Check event requirements
        if len(self.event.attributes) == 1 and \
                self.event.attributes[0]['type'] == 'AccountId':
            account_id = self.event.attributes[0]['value'].replace('0x', '')

            self.block._accounts_new.append(account_id)

            account_audit = AccountAudit(
                account_id=account_id,
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=ACCOUNT_AUDIT_TYPE_NEW
            )

            account_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in AccountAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_ACCOUNT_CREATED,
            account_id=self.event.attributes.replace('0x', '')
        )

        search_index.save(db_session)


class ReapedAccount(EventProcessor):
    module_id = 'Balances'
    event_id = 'ReapedAccount'

    def accumulation_hook(self, db_session):
        # Check event requirements
        if len(self.event.attributes) == 1 and \
                self.event.attributes[0]['type'] == 'AccountId':

            account_id = self.event.attributes[0]['value'].replace('0x', '')

        elif len(self.event.attributes) == 2 and \
                self.event.attributes[0]['type'] == 'AccountId' and \
                self.event.attributes[1]['type'] == 'Balance':

            account_id = self.event.attributes[0]['value'].replace('0x', '')
        else:
            raise ValueError('Event doensn\'t meet requirements')

        self.block._accounts_reaped.append(account_id)

        account_audit = AccountAudit(
            account_id=account_id,
            block_id=self.event.block_id,
            extrinsic_idx=self.event.extrinsic_idx,
            event_idx=self.event.event_idx,
            type_id=ACCOUNT_AUDIT_TYPE_REAPED
        )

        account_audit.save(db_session)

        # Insert account index audit record

        new_account_index_audit = AccountIndexAudit(
            account_index_id=None,
            account_id=account_id,
            block_id=self.event.block_id,
            extrinsic_idx=self.event.extrinsic_idx,
            event_idx=self.event.event_idx,
            type_id=ACCOUNT_INDEX_AUDIT_TYPE_REAPED
        )

        new_account_index_audit.save(db_session)

    def accumulation_revert(self, db_session):

        for item in AccountIndexAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)

        for item in AccountAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_ACCOUNT_KILLED,
            account_id=self.event.attributes[0]['value'].replace('0x', '')
        )

        search_index.save(db_session)


class KilledAccount(EventProcessor):
    module_id = 'System'
    event_id = 'KilledAccount'

    def accumulation_hook(self, db_session):
        print("KilledAccount")
        print(self.event.attributes)
        # Check event requirements
        if len(self.event.attributes) == 1 and \
                self.event.attributes[0]['type'] == 'AccountId':

            account_id = self.event.attributes[0]['value'].replace('0x', '')
        else:
            raise ValueError('Event doensn\'t meet requirements')

        self.block._accounts_reaped.append(account_id)

        account_audit = AccountAudit(
            account_id=account_id,
            block_id=self.event.block_id,
            extrinsic_idx=self.event.extrinsic_idx,
            event_idx=self.event.event_idx,
            type_id=ACCOUNT_AUDIT_TYPE_REAPED
        )

        account_audit.save(db_session)

    def accumulation_revert(self, db_session):

        for item in AccountAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_ACCOUNT_KILLED,
            account_id=self.event.attributes[0].replace('0x', '')
        )

        search_index.save(db_session)


class NewAccountIndexEventProcessor(EventProcessor):
    module_id = 'Indices'
    event_id = 'NewAccountIndex'

    def accumulation_hook(self, db_session):
        account_id = self.event.attributes[0].replace('0x', '')
        id = self.event.attributes[1]

        account_index_audit = AccountIndexAudit(
            account_index_id=id,
            account_id=account_id,
            block_id=self.event.block_id,
            extrinsic_idx=self.event.extrinsic_idx,
            event_idx=self.event.event_idx,
            type_id=ACCOUNT_INDEX_AUDIT_TYPE_NEW
        )

        account_index_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in AccountIndexAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class IndexAssignedEventProcessor(EventProcessor):
    module_id = 'Indices'
    event_id = 'IndexAssigned'

    def accumulation_hook(self, db_session):
        account_id = self.event.attributes[0]['value'].replace('0x', '')
        id = self.event.attributes[1]['value']

        account_index_audit = AccountIndexAudit(
            account_index_id=id,
            account_id=account_id,
            block_id=self.event.block_id,
            extrinsic_idx=self.event.extrinsic_idx,
            event_idx=self.event.event_idx,
            type_id=ACCOUNT_INDEX_AUDIT_TYPE_NEW
        )

        account_index_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in AccountIndexAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class IndexFreedEventProcessor(EventProcessor):
    module_id = 'Indices'
    event_id = 'IndexFreed'

    def accumulation_hook(self, db_session):
        account_index = self.event.attributes[0]['value']

        new_account_index_audit = AccountIndexAudit(
            account_index_id=account_index,
            account_id=None,
            block_id=self.event.block_id,
            extrinsic_idx=self.event.extrinsic_idx,
            event_idx=self.event.event_idx,
            type_id=ACCOUNT_INDEX_AUDIT_TYPE_REAPED
        )

        new_account_index_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in AccountIndexAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)


class ProposedEventProcessor(EventProcessor):
    module_id = 'Democracy'
    event_id = 'Proposed'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_DEMOCRACY_PROPOSE,
            account_id=self.extrinsic.address,
            sorting_value=self.extrinsic.params[1]['value']
        )

        search_index.save(db_session)


class TechCommProposedEventProcessor(EventProcessor):
    module_id = 'Technicalcommittee'
    event_id = 'Proposed'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_TECHCOMM_PROPOSED,
            account_id=self.extrinsic.address
        )

        search_index.save(db_session)


class TechCommVotedEventProcessor(EventProcessor):
    module_id = 'Technicalcommittee'
    event_id = 'Voted'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_TECHCOMM_VOTED,
            account_id=self.extrinsic.address
        )

        search_index.save(db_session)


class TreasuryAwardedEventProcessor(EventProcessor):
    module_id = 'Treasury'
    event_id = 'Awarded'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_TREASURY_AWARDED,
            account_id=self.event.attributes[2]['value'].replace('0x', ''),
            sorting_value=self.event.attributes[1]['value']
        )

        search_index.save(db_session)


class CodeStoredEventProcessor(EventProcessor):
    module_id = 'Contract'
    event_id = 'CodeStored'

    def accumulation_hook(self, db_session):

        self.block.count_contracts_new += 1

        contract = Contract(
            code_hash=self.event.attributes[0]['value'].replace('0x', ''),
            created_at_block=self.event.block_id,
            created_at_extrinsic=self.event.extrinsic_idx,
            created_at_event=self.event.event_idx,
        )

        for param in self.extrinsic.params:
            if param.get('name') == 'code':
                contract.bytecode = param.get('value')

        contract.save(db_session)

    def accumulation_revert(self, db_session):
        for item in Contract.query(db_session).filter_by(created_at_block=self.block.id):
            db_session.delete(item)


class SlashEventProcessor(EventProcessor):
    module_id = 'Staking'
    event_id = 'Slash'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=SEARCH_INDEX_SLASHED_ACCOUNT,
            account_id=self.event.attributes[0]['value'].replace('0x', ''),
            sorting_value=self.event.attributes[1]['value']
        )

        search_index.save(db_session)


class BalancesTransferProcessor(EventProcessor):
    module_id = 'Balances'
    event_id = 'Transfer'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=SEARCH_INDEX_BALANCETRANSFER,
            account_id=self.event.attributes[0]['value'].replace('0x', ''),
            sorting_value=self.event.attributes[2]['value']
        )

        search_index.save(db_session)

        search_index = self.add_search_index(
            index_type_id=SEARCH_INDEX_BALANCETRANSFER,
            account_id=self.event.attributes[1]['value'].replace('0x', ''),
            sorting_value=self.event.attributes[2]['value']
        )

        search_index.save(db_session)


class BalancesDeposit(EventProcessor):
    module_id = 'Balances'
    event_id = 'Deposit'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_BALANCES_DEPOSIT,
            account_id=self.event.attributes[0].replace('0x', ''),
            sorting_value=self.event.attributes[1]
        )

        search_index.save(db_session)


class HeartbeatReceivedEventProcessor(EventProcessor):
    module_id = 'imonline'
    event_id = 'HeartbeatReceived'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=SEARCH_INDEX_HEARTBEATRECEIVED,
            # account_id=self.event.attributes[0]['value'].replace('0x', ''),
            account_id=self.event.attributes.replace('0x', ''),
            sorting_value=None
        )

        search_index.save(db_session)


class SomeOffline(EventProcessor):
    module_id = 'imonline'
    event_id = 'SomeOffline'

    def process_search_index(self, db_session):
        for item in self.event.attributes[0]['value']:
            search_index = self.add_search_index(
                index_type_id=settings.SEARCH_INDEX_IMONLINE_SOMEOFFLINE,
                account_id=item['validatorId'].replace('0x', ''),
                sorting_value=None
            )

            search_index.save(db_session)


class IdentitySetEventProcessor(EventProcessor):
    module_id = 'identity'
    event_id = 'IdentitySet'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 1 and \
                self.event.attributes[0]['type'] == 'AccountId':

            identity_audit = IdentityAudit(
                account_id=self.event.attributes[0]['value'].replace('0x', ''),
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=IDENTITY_TYPE_SET
            )

            identity_audit.data = {
                'display': None,
                'email': None,
                'legal': None,
                'riot': None,
                'web': None,
                'twitter': None
            }

            for param in self.extrinsic.params:
                if param.get('name') == 'info':
                    identity_audit.data['display'] = param.get('value', {}).get('display', {}).get('Raw')
                    identity_audit.data['email'] = param.get('value', {}).get('email', {}).get('Raw')
                    identity_audit.data['legal'] = param.get('value', {}).get('legal', {}).get('Raw')
                    identity_audit.data['web'] = param.get('value', {}).get('web', {}).get('Raw')
                    identity_audit.data['riot'] = param.get('value', {}).get('riot', {}).get('Raw')
                    identity_audit.data['twitter'] = param.get('value', {}).get('twitter', {}).get('Raw')

            identity_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in IdentityAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_IDENTITY_SET,
            account_id=self.event.attributes[0]['value'].replace('0x', '')
        )

        search_index.save(db_session)


class IdentityClearedEventProcessor(EventProcessor):
    module_id = 'identity'
    event_id = 'IdentityCleared'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 2 and \
                self.event.attributes[0]['type'] == 'AccountId' and \
                self.event.attributes[1]['type'] == 'Balance':
            identity_audit = IdentityAudit(
                account_id=self.event.attributes[0]['value'].replace('0x', ''),
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=IDENTITY_TYPE_CLEARED
            )

            identity_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in IdentityAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_IDENTITY_CLEARED,
            account_id=self.event.attributes[0]['value'].replace('0x', '')
        )

        search_index.save(db_session)


class IdentityKilledEventProcessor(EventProcessor):
    module_id = 'identity'
    event_id = 'IdentityKilled'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 2 and \
                self.event.attributes[0]['type'] == 'AccountId' and \
                self.event.attributes[1]['type'] == 'Balance':
            identity_audit = IdentityAudit(
                account_id=self.event.attributes[0]['value'].replace('0x', ''),
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=IDENTITY_TYPE_KILLED
            )

            identity_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in IdentityAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_IDENTITY_KILLED,
            account_id=self.event.attributes[0]['value'].replace('0x', '')
        )

        search_index.save(db_session)


class IdentityJudgementGivenEventProcessor(EventProcessor):
    module_id = 'identity'
    event_id = 'JudgementGiven'

    def accumulation_hook(self, db_session):

        # Check event requirements
        if len(self.event.attributes) == 2 and \
                self.event.attributes[0]['type'] == 'AccountId' and \
                self.event.attributes[1]['type'] == 'RegistrarIndex':

            identity_audit = IdentityJudgementAudit(
                account_id=self.event.attributes[0]['value'].replace('0x', ''),
                registrar_index=self.event.attributes[1]['value'],
                block_id=self.event.block_id,
                extrinsic_idx=self.event.extrinsic_idx,
                event_idx=self.event.event_idx,
                type_id=IDENTITY_JUDGEMENT_TYPE_GIVEN
            )

            for param in self.extrinsic.params:
                if param.get('name') == 'judgement':
                    identity_audit.data = {'judgement': list(param.get('value').keys())[0]}

            identity_audit.save(db_session)

    def accumulation_revert(self, db_session):
        for item in IdentityJudgementAudit.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_IDENTITY_JUDGEMENT_GIVEN,
            account_id=self.event.attributes[0]['value'].replace('0x', '')
        )

        search_index.save(db_session)


class IdentityJudgementRequested(EventProcessor):
    module_id = 'identity'
    event_id = 'JudgementRequested'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_IDENTITY_JUDGEMENT_REQUESTED,
            account_id=self.event.attributes[0]['value'].replace('0x', '')
        )

        search_index.save(db_session)


class IdentityJudgementUnrequested(EventProcessor):
    module_id = 'identity'
    event_id = 'JudgementUnrequested'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_IDENTITY_JUDGEMENT_UNREQUESTED,
            account_id=self.event.attributes[0]['value'].replace('0x', '')
        )

        search_index.save(db_session)


class CouncilNewTermEventProcessor(EventProcessor):
    module_id = 'electionsphragmen'
    event_id = 'NewTerm'

    def sequencing_hook(self, db_session, parent_block, parent_sequenced_block):
        new_member_ids = [
            member_struct['account'].replace('0x', '') for member_struct in self.event.attributes[0]['value']
        ]

        Account.query(db_session).filter(
            Account.id.in_(new_member_ids), Account.was_council_member == False
        ).update({Account.was_council_member: True}, synchronize_session='fetch')

        Account.query(db_session).filter(
            Account.id.notin_(new_member_ids), Account.is_council_member == True
        ).update({Account.is_council_member: False}, synchronize_session='fetch')

        Account.query(db_session).filter(
            Account.id.in_(new_member_ids), Account.is_council_member == False
        ).update({Account.is_council_member: True}, synchronize_session='fetch')

    def process_search_index(self, db_session):
        for member_struct in self.event.attributes[0]['value']:
            search_index = self.add_search_index(
                index_type_id=settings.SEARCH_INDEX_COUNCIL_MEMBER_ELECTED,
                account_id=member_struct['account'].replace('0x', ''),
                sorting_value=member_struct['balance']
            )

            search_index.save(db_session)


class CouncilMemberKicked(EventProcessor):
    module_id = 'electionsphragmen'
    event_id = 'MemberKicked'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_COUNCIL_MEMBER_KICKED,
            account_id=self.event.attributes[0]['value'].replace('0x', '')
        )

        search_index.save(db_session)


class CouncilMemberRenounced(EventProcessor):
    module_id = 'electionsphragmen'
    event_id = 'MemberRenounced'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_COUNCIL_CANDIDACY_RENOUNCED,
            account_id=self.event.attributes[0]['value'].replace('0x', '')
        )

        search_index.save(db_session)


class CouncilProposedEventProcessor(EventProcessor):
    module_id = 'council'
    event_id = 'Proposed'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_COUNCIL_PROPOSED,
            account_id=self.event.attributes[0]['value'].replace('0x', '')
        )

        search_index.save(db_session)


class CouncilVotedEventProcessor(EventProcessor):
    module_id = 'council'
    event_id = 'Voted'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_COUNCIL_VOTE,
            account_id=self.event.attributes.replace('0x', '')
        )

        search_index.save(db_session)


class RegistrarAddedEventProcessor(EventProcessor):
    module_id = 'identity'
    event_id = 'RegistrarAdded'

    def sequencing_hook(self, db_session, parent_block, parent_sequenced_block):
        registrars = self.substrate.get_runtime_state(
            module="Identity",
            storage_function="Registrars",
            params=[]
        ).get('result')

        if not registrars:
            registrars = []

        registrar_ids = [registrar['account'].replace('0x', '') for registrar in registrars]

        Account.query(db_session).filter(
            Account.id.in_(registrar_ids), Account.was_registrar == False
        ).update({Account.was_registrar: True}, synchronize_session='fetch')

        Account.query(db_session).filter(
            Account.id.notin_(registrar_ids), Account.is_registrar == True
        ).update({Account.is_registrar: False}, synchronize_session='fetch')

        Account.query(db_session).filter(
            Account.id.in_(registrar_ids), Account.is_registrar == False
        ).update({Account.is_registrar: True}, synchronize_session='fetch')


class StakingBonded(EventProcessor):
    module_id = 'staking'
    event_id = 'Bonded'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_STAKING_BONDED,
            account_id=self.event.attributes[0]['value'].replace('0x', ''),
            sorting_value=self.event.attributes[1]['value']
        )

        search_index.save(db_session)


class StakingUnbonded(EventProcessor):
    module_id = 'staking'
    event_id = 'Unbonded'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_STAKING_UNBONDED,
            account_id=self.event.attributes[0]['value'].replace('0x', ''),
            sorting_value=self.event.attributes[1]['value']
        )

        search_index.save(db_session)


class StakingWithdrawn(EventProcessor):
    module_id = 'staking'
    event_id = 'Withdrawn'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_STAKING_WITHDRAWN,
            account_id=self.event.attributes[0].replace('0x', ''),
            sorting_value=self.event.attributes[1]
        )

        search_index.save(db_session)


class ClaimsClaimed(EventProcessor):
    module_id = 'claims'
    event_id = 'Claimed'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=settings.SEARCH_INDEX_CLAIMS_CLAIMED,
            account_id=self.event.attributes[0].replace('0x', ''),
            sorting_value=self.event.attributes[2]
        )

        search_index.save(db_session)
