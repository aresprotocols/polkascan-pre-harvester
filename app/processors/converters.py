#  Polkascan PRE Harvester
#
#  Copyright 2018-2020 openAware BV (NL).
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
#  converters.py
import json
import logging
import math
import traceback
from datetime import datetime

from scalecodec.base import ScaleBytes, RuntimeConfiguration
from scalecodec.exceptions import RemainingScaleBytesNotEmptyException
from scalecodec.type_registry import load_type_registry_file
from sqlalchemy import func, distinct
from sqlalchemy.exc import SQLAlchemyError
from substrateinterface import logger
from substrateinterface.exceptions import SubstrateRequestException
from substrateinterface.utils.hasher import xxh128

from app import settings, utils
from app.extend.base import AresSubstrateInterface, CompatibleRuntimeConfiguration
from app.models.data import Extrinsic, Block, Event, Runtime, RuntimeModule, RuntimeCall, RuntimeCallParam, \
    RuntimeEvent, RuntimeEventAttribute, RuntimeType, RuntimeStorage, BlockTotal, RuntimeConstant, AccountAudit, \
    AccountIndexAudit, ReorgBlock, ReorgExtrinsic, ReorgEvent, ReorgLog, RuntimeErrorMessage, Account, \
    AccountInfoSnapshot, SearchIndex, SymbolSnapshot
from app.models.harvester import Status
from app.processors import NewSessionEventProcessor, Log
from app.processors.base import BaseService, ProcessorRegistry
from app.processors.events.oracle.aggregated_price import AggregatedPriceEventProcessor

if settings.DEBUG:
    # Set Logger level to Debug
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    logger.addHandler(ch)


class HarvesterCouldNotAddBlock(Exception):
    pass


class BlockAlreadyAdded(Exception):
    pass


class BlockIntegrityError(Exception):
    pass


class PolkascanHarvesterService(BaseService):

    def __init__(self, db_session, type_registry='default', type_registry_file=None):
        self.db_session = db_session

        if type_registry_file:
            custom_type_registry = load_type_registry_file(type_registry_file)
        else:
            custom_type_registry = None

        print('RUN KAMI-PolkascanHarvesterService')
        self.substrate = AresSubstrateInterface(
            url=settings.SUBSTRATE_RPC_URL,
            type_registry=custom_type_registry,
            type_registry_preset=type_registry,
            runtime_config=CompatibleRuntimeConfiguration()
        )
        print('RUN KAMI-DEBUG runtime-version:{}'.format(self.substrate.runtime_version))
        self.metadata_store = {}

    def process_genesis(self, block):
        self.substrate.init_runtime(block_hash=block.hash)
        # Set block time of parent block
        child_block = Block.query(self.db_session).filter_by(parent_hash=block.hash).first()
        if child_block.datetime:
            block.set_datetime(child_block.datetime)

        # Retrieve genesis accounts
        if settings.get_versioned_setting('SUBSTRATE_STORAGE_INDICES', block.spec_version_id) == 'Accounts':

            # Get accounts from storage keys
            storage_key_prefix = self.substrate.generate_storage_hash(
                storage_module='System',
                storage_function='Account'
            )

            rpc_result = self.substrate.rpc_request(
                'state_getKeys',
                [storage_key_prefix, block.hash]
            ).get('result')
            # Extract accounts from storage key
            genesis_accounts = [storage_key[-64:] for storage_key in rpc_result if len(storage_key) == 162]

            for account_id in genesis_accounts:
                account_audit = AccountAudit(
                    account_id=account_id,
                    block_id=block.id,
                    extrinsic_idx=None,
                    event_idx=None,
                    type_id=settings.ACCOUNT_AUDIT_TYPE_NEW
                )

                account_audit.save(self.db_session)

            block.count_accounts_new = len(genesis_accounts)
            block.count_accounts = len(genesis_accounts)

        elif settings.get_versioned_setting('SUBSTRATE_STORAGE_INDICES', block.spec_version_id) == 'EnumSet':

            genesis_account_page_count = self.substrate.get_runtime_state(
                module="Indices",
                storage_function="NextEnumSet",
                block_hash=block.hash
            ).get('result', 0)

            # Get Accounts on EnumSet
            block.count_accounts_new = 0
            block.count_accounts = 0

            for enum_set_nr in range(0, genesis_account_page_count + 1):

                genesis_accounts = self.substrate.get_runtime_state(
                    module="Indices",
                    storage_function="EnumSet",
                    params=[enum_set_nr],
                    block_hash=block.hash
                ).get('result')

                if genesis_accounts:
                    block.count_accounts_new += len(genesis_accounts)
                    block.count_accounts += len(genesis_accounts)

                    for idx, account_id in enumerate(genesis_accounts):
                        account_audit = AccountAudit(
                            account_id=account_id.replace('0x', ''),
                            block_id=block.id,
                            extrinsic_idx=None,
                            event_idx=None,
                            type_id=settings.ACCOUNT_AUDIT_TYPE_NEW
                        )

                        account_audit.save(self.db_session)

                        account_index_id = enum_set_nr * 64 + idx

                        account_index_audit = AccountIndexAudit(
                            account_index_id=account_index_id,
                            account_id=account_id.replace('0x', ''),
                            block_id=block.id,
                            extrinsic_idx=None,
                            event_idx=None,
                            type_id=settings.ACCOUNT_INDEX_AUDIT_TYPE_NEW
                        )

                        account_index_audit.save(self.db_session)

        block.save(self.db_session)

        # Add hardcoded account like treasury stored in settings
        for account_id in settings.SUBSTRATE_TREASURY_ACCOUNTS:
            account_audit = AccountAudit(
                account_id=account_id,
                block_id=block.id,
                extrinsic_idx=None,
                event_idx=None,
                data={'is_treasury': True},
                type_id=settings.ACCOUNT_AUDIT_TYPE_NEW
            )

            account_audit.save(self.db_session)

        # Check for sudo accounts
        try:
            # Update sudo key
            sudo_key = utils.query_storage(pallet_name="Sudo", storage_name="Key", substrate=self.substrate,
                                           block_hash=block.hash).value
            account_audit = AccountAudit(
                account_id=sudo_key.replace('0x', ''),
                block_id=block.id,
                extrinsic_idx=None,
                event_idx=None,
                data={'is_sudo': True},
                type_id=settings.ACCOUNT_AUDIT_TYPE_NEW
            )

            account_audit.save(self.db_session)
        except ValueError:
            pass

        # Create initial session
        initial_session_event = NewSessionEventProcessor(
            block=block, event=Event(), substrate=self.substrate
        )

        if settings.get_versioned_setting('NEW_SESSION_EVENT_HANDLER', block.spec_version_id):
            initial_session_event.add_session(db_session=self.db_session, session_id=0)
        else:
            initial_session_event.add_session_old(db_session=self.db_session, session_id=0)

        # Retrieve technical committee members
        members = utils.query_storage(pallet_name="TechnicalCommittee", storage_name="Members",
                                      substrate=self.substrate,
                                      block_hash=block.hash)

        if members is not None:
            members = [v.replace('0x', '') for v in members.value]
            for account_id in members:
                account_audit = AccountAudit(
                    account_id=account_id,
                    block_id=block.id,
                    extrinsic_idx=None,
                    event_idx=None,
                    data={'is_tech_comm_member': True},
                    type_id=settings.ACCOUNT_AUDIT_TYPE_NEW
                )
                account_audit.save(self.db_session)

    ###
    #  before process_metadata get_block had called init_runtime
    ###
    def process_metadata(self, spec_version, block_hash):
        print('Kami Debug spec_version={}, block_hash={},'.format(spec_version, block_hash))
        # Check if metadata already stored
        runtime = Runtime.query(self.db_session).get(spec_version)

        if runtime:

            if spec_version in self.substrate.metadata_cache:
                self.metadata_store[spec_version] = self.substrate.metadata_cache[spec_version]
            else:
                # self.substrate.init_runtime(block_hash)
                # What do?
                self.metadata_store[spec_version] = self.substrate.metadata_decoder

        else:
            print('Metadata: CACHE MISS', spec_version)

            runtime_version_data = self.substrate.get_block_runtime_version(block_hash)
            # Call and get runtime infos.
            self.substrate.init_runtime(block_hash)
            modules = self.substrate.metadata_decoder.pallets

            # self.db_session.begin(subtransactions=True)
            savepoint = self.db_session.begin_nested()
            try:

                # Store metadata in database
                runtime = Runtime(
                    id=spec_version,
                    impl_name=runtime_version_data["implName"],
                    impl_version=runtime_version_data["implVersion"],
                    spec_name=runtime_version_data["specName"],
                    spec_version=spec_version,
                    json_metadata=str(self.substrate.metadata_decoder.data),
                    json_metadata_decoded=self.substrate.metadata_decoder.value,
                    apis=runtime_version_data["apis"],
                    authoring_version=runtime_version_data["authoringVersion"],
                    count_call_functions=0,
                    count_events=0,
                    count_modules=len(modules),
                    count_storage_functions=0,
                    count_constants=0,
                    count_errors=0
                )

                runtime.save(self.db_session)

                print('store version to db', spec_version)

                for module_index, module in enumerate(modules):

                    if hasattr(module, 'index'):
                        module_index = module.index

                    # Check if module exists
                    if RuntimeModule.query(self.db_session).filter_by(
                            spec_version=spec_version,
                            module_id=module.get_identifier()
                    ).count() == 0:
                        module_id = module.get_identifier()
                    else:
                        module_id = '{}_1'.format(module.get_identifier())

                    # Storage backwards compt check
                    if module.storage and isinstance(module.storage, list):
                        storage_functions = module.storage
                    elif module.storage and isinstance(getattr(module.storage, 'value'), dict):
                        storage_functions = module.storage.items
                    else:
                        storage_functions = []

                    if len(storage_functions) > 0:
                        prefix = module.value.get('storage').get('prefix')
                    else:
                        prefix = None

                    runtime_module = RuntimeModule(
                        spec_version=spec_version,
                        module_id=module_id,
                        prefix=prefix,
                        name=module.name,
                        count_call_functions=len(module.calls or []),
                        count_storage_functions=len(storage_functions),
                        count_events=len(module.events or []),
                        count_constants=len(module.constants or []),
                        count_errors=len(module.errors or []),
                    )
                    runtime_module.save(self.db_session)

                    # Update totals in runtime
                    runtime.count_call_functions += runtime_module.count_call_functions
                    runtime.count_events += runtime_module.count_events
                    runtime.count_storage_functions += runtime_module.count_storage_functions
                    runtime.count_constants += runtime_module.count_constants
                    runtime.count_errors += runtime_module.count_errors

                    if len(module.calls or []) > 0:
                        for idx, call in enumerate(module.calls):
                            call.lookup = "{:02x}{:02x}".format(module_index, idx)
                            runtime_call = RuntimeCall(
                                spec_version=spec_version,
                                module_id=module_id,
                                # call_id=call.get_identifier(),
                                call_id=call.name,
                                index=idx,
                                name=call.name,
                                lookup=call.lookup,
                                documentation='\n'.join(call.docs),
                                count_params=len(call.args)
                            )
                            runtime_call.save(self.db_session)

                            for arg in call.args:
                                runtime_call_param = RuntimeCallParam(
                                    runtime_call_id=runtime_call.id,
                                    name=arg.name,
                                    type=arg.type
                                )
                                runtime_call_param.save(self.db_session)

                    if len(module.events or []) > 0:

                        for event_index, event in enumerate(module.events):

                            event.lookup = "{:02x}{:02x}".format(module_index, event_index)
                            runtime_event = RuntimeEvent(
                                spec_version=spec_version,
                                module_id=module_id,
                                event_id=event.name,
                                index=event_index,
                                name=event.name,
                                lookup=event.lookup,
                                documentation='\n'.join(event.docs),
                                count_attributes=len(event.args)
                            )
                            runtime_event.save(self.db_session)

                            for arg_index, arg in enumerate(event.args):
                                runtime_event_attr = RuntimeEventAttribute(
                                    runtime_event_id=runtime_event.id,
                                    index=arg_index,
                                    type=arg.value
                                )
                                runtime_event_attr.save(self.db_session)

                    if len(storage_functions) > 0:
                        for idx, storage in enumerate(storage_functions):
                            types = storage.get_params_type_string()
                            value_type = storage.get_value_type_string()
                            hashers = storage.get_param_hashers()

                            hasher_type1 = None
                            hasher_type2 = None
                            key_type1 = None
                            key_type2 = None
                            type_is_linked = None

                            if len(hashers) == 1:
                                hasher_type1 = hashers[0]
                            elif len(hashers) == 2:
                                hasher_type1 = hashers[0]
                                hasher_type2 = hashers[1]

                            if len(types) == 1:
                                key_type1 = types[0]
                            elif len(types) == 2:
                                key_type1 = types[0]
                                key_type2 = types[1]

                            _prefix = module.value_object['storage'].value_object['prefix']
                            runtime_storage = RuntimeStorage(
                                spec_version=spec_version,
                                module_id=module_id,
                                index=idx,
                                name=storage.name,
                                lookup=None,
                                default=storage.value.get('default'),
                                modifier=storage.modifier,
                                type_hasher=hasher_type1,
                                storage_key=xxh128(_prefix.data.data) + xxh128(storage.name.encode()),
                                type_key1=key_type1,
                                type_key2=key_type2,
                                type_value=value_type,
                                type_is_linked=type_is_linked,
                                type_key2hasher=hasher_type2
                            )
                            runtime_storage.save(self.db_session)

                    if len(module.constants or []) > 0:
                        for idx, constant in enumerate(module.constants):
                            # Decode value
                            try:
                                constant_value = constant.value_object['value'].value_object
                                decode_constant_type = constant.type if self.substrate.implements_scaleinfo() else constant.value.get(
                                    "type")
                                value_obj = self.substrate.runtime_config.create_scale_object(
                                    decode_constant_type, data=ScaleBytes(constant_value)
                                )
                                value_obj.decode()
                                constant_type = value_obj.type_name if self.substrate.implements_scaleinfo() and hasattr(
                                    value_obj, "type_name") else constant.type
                                value = value_obj.serialize()
                            except ValueError:
                                print("constant error:1, type:{}, name:{}", constant.type, constant.name)
                                value = constant.value_object['value'].serialize()
                            except RemainingScaleBytesNotEmptyException:
                                print("constant error:2, type:{}, name:{}", constant.type, constant.name)
                                value = constant.value_object['value'].serialize()
                            except NotImplementedError:
                                print("constant error:3, type:{}, name:{}", constant.type, constant.name)
                                value = constant.value_object['value'].serialize()

                            if type(value) is list or type(value) is dict:
                                value = json.dumps(value)

                            runtime_constant = RuntimeConstant(
                                spec_version=spec_version,
                                module_id=module_id,
                                index=idx,
                                name=constant.name,
                                type=constant_type,
                                value=value
                            )
                            runtime_constant.save(self.db_session)

                    if len(module.errors or []) > 0:
                        for idx, error in enumerate(module.errors):
                            runtime_error = RuntimeErrorMessage(
                                spec_version=spec_version,
                                module_id=module_id,
                                module_index=module_index,
                                index=idx,
                                name=error.name
                            )
                            runtime_error.save(self.db_session)

                    runtime.save(self.db_session)

                # Process types
                for runtime_type_data in list(self.substrate.get_type_registry(block_hash=block_hash).values()):
                    runtime_type = RuntimeType(
                        spec_version=runtime_type_data["spec_version"],
                        type_string=runtime_type_data["type_string"],
                        decoder_class=runtime_type_data["decoder_class"],
                        is_primitive_core=runtime_type_data["is_primitive_core"],
                        is_primitive_runtime=runtime_type_data["is_primitive_runtime"]
                    )
                    runtime_type.save(self.db_session)

                savepoint.commit()
                self.db_session.commit()
                # Put in local store
                self.metadata_store[spec_version] = self.substrate.metadata_decoder
            except SQLAlchemyError as e:
                print(e)
                savepoint.rollback()

    def add_block(self, block_hash):




        # Check if block is already process
        print('Add block hash = ', block_hash)
        if Block.query(self.db_session).filter_by(hash=block_hash).count() > 0:
            # self.remove_block(block_hash=block_hash)
            raise BlockAlreadyAdded(block_hash)
            # remove old data


        if settings.SUBSTRATE_MOCK_EXTRINSICS:
            self.substrate.mock_extrinsics = settings.SUBSTRATE_MOCK_EXTRINSICS

        json_block = self.substrate.get_block(block_hash, include_author=False)
        header = json_block['header']
        parent_hash = header['parentHash']
        block_id = header['number']
        extrinsics_root = header['extrinsicsRoot']
        state_root = header['stateRoot']
        digest_logs = []
        for idx, log_data in enumerate(header.get('digest', {}).get('logs', [])):
            digest_logs.append(log_data.data.to_hex())

        # ==== Get block runtime from Substrate ==================

        self.process_metadata(self.substrate.runtime_version, block_hash)

        # ==== Get parent block runtime ===================

        if block_id > 0:
            json_parent_runtime_version = self.substrate.get_block_runtime_version(parent_hash)

            parent_spec_version = json_parent_runtime_version.get('specVersion', 0)

            self.process_metadata(parent_spec_version, parent_hash)
        else:
            parent_spec_version = self.substrate.runtime_version

        # ==== Set initial block properties =====================

        block = Block(
            id=block_id,
            parent_id=block_id - 1,
            hash=block_hash,
            parent_hash=parent_hash,
            state_root=state_root,
            extrinsics_root=extrinsics_root,
            count_extrinsics=0,
            count_events=0,
            count_accounts_new=0,
            count_accounts_reaped=0,
            count_accounts=0,
            count_events_extrinsic=0,
            count_events_finalization=0,
            count_events_module=0,
            count_events_system=0,
            count_events_transfer=0,
            count_extrinsics_error=0,
            count_extrinsics_signed=0,
            count_extrinsics_signedby_address=0,
            count_extrinsics_signedby_index=0,
            count_extrinsics_success=0,
            count_extrinsics_unsigned=0,
            count_sessions_new=0,
            count_contracts_new=0,
            count_log=0,
            range10000=math.floor(block_id / 10000),
            range100000=math.floor(block_id / 100000),
            range1000000=math.floor(block_id / 1000000),
            spec_version_id=self.substrate.runtime_version,
            logs=digest_logs
        )

        # Set temp helper variables
        block._accounts_new = []
        block._accounts_reaped = []

        # ==== Get block events from Substrate ==================
        extrinsic_success_idx = {}
        events = []

        try:
            # TODO implemented solution in substrate interface for runtime transition blocks
            # Events are decoded against runtime of parent block
            RuntimeConfiguration().set_active_spec_version_id(parent_spec_version)
            # print('blck_hash', block_hash)
            # print('parent_spec_version', parent_spec_version)
            # events_decoder = self.substrate.get_block_events(block_hash, self.metadata_store[parent_spec_version])
            events_decoder = self.substrate.get_events(block_hash)
            # print('events_decoder', events_decoder)
            # Revert back to current runtime
            RuntimeConfiguration().set_active_spec_version_id(block.spec_version_id)

            event_idx = 0

            for event in events_decoder:
                event.value['module_id'] = event.value['module_id'].lower()
                # print('module_id', event.value['module_id'])
                # print('event.value', event.value)
                model = Event(
                    block_id=block_id,
                    event_idx=event_idx,
                    phase=event.value_object['phase'].index,
                    extrinsic_idx=event.value['extrinsic_idx'],
                    type=event.value.get('event_index') or event.value.get('type'),
                    spec_version_id=parent_spec_version,
                    module_id=event.value['module_id'],
                    event_id=event.value['event_id'],
                    system=int(event.value['module_id'] == 'system'),
                    module=int(event.value['module_id'] != 'system'),
                    # attributes=event.value['params'],
                    attributes=event.params,
                    codec_error=False
                )

                # Process event
                if model.module_id == 'balances' and model.event_id == 'Transfer':
                    block.count_events_transfer += 1

                if event.value_object['phase'].index == 0:
                    block.count_events_extrinsic += 1
                elif event.value_object['phase'].index == 1:
                    block.count_events_finalization += 1

                if event.value['module_id'] == 'system':

                    block.count_events_system += 1

                    # Store result of extrinsic
                    if event.value['event_id'] == 'ExtrinsicSuccess':
                        extrinsic_success_idx[event.value['extrinsic_idx']] = True
                        block.count_extrinsics_success += 1

                    if event.value['event_id'] == 'ExtrinsicFailed':
                        extrinsic_success_idx[event.value['extrinsic_idx']] = False
                        block.count_extrinsics_error += 1
                else:

                    block.count_events_module += 1

                model.save(self.db_session)

                events.append(model)

                event_idx += 1

            block.count_events = len(events_decoder)

        except SubstrateRequestException:
            block.count_events = 0

        # === Extract extrinsics from block ====

        extrinsics_data = json_block['extrinsics']

        block.count_extrinsics = len(extrinsics_data)

        extrinsic_idx = 0

        extrinsics = []

        for extrinsic in extrinsics_data:

            extrinsic_success = extrinsic_success_idx.get(extrinsic_idx, False)

            # contains_transaction = int(extrinsic_data.get('version_info'), 16) >= 80

            # if extrinsics_decoder.era:
            #     era = extrinsics_decoder.era.raw_value
            # else:
            value = extrinsic.value
            print(value)
            print("=====extrinsic.value=====")
            print(extrinsic.value_object)
            era = None
            if 'era' in value:
                era = ','.join(map(str, value.get('era')))

            signature = None
            if 'signature' in value:
                t = value.get('signature')
                signature = list(t.values())[0].replace('0x', '')

            version_info = '04'
            extrinsic_hash = value.get('extrinsic_hash')
            address = None
            if 'address' in value:
                version_info = '84'
                address = value.get('address').replace('0x', '')
            if extrinsic_hash is not None:
                extrinsic_hash = extrinsic_hash[2:]  # replace '0x'

            model = Extrinsic(
                block_id=block_id,
                extrinsic_idx=extrinsic_idx,
                extrinsic_hash=extrinsic_hash,
                extrinsic_length=value.get('extrinsic_length'),
                extrinsic_version=version_info,
                signed=extrinsic.signed,
                unsigned=not extrinsic.signed,
                signedby_address=bool(extrinsic.signed and 'address' in value),
                signedby_index=bool(extrinsic.signed and 'account_index' in value),
                address_length=value.get('account_length', None),
                address=address,
                account_index=value.get('account_index', None),
                account_idx=value.get('account_idx', None),
                signature=signature,
                nonce=value.get('nonce', None),
                era=era,
                call=value.get('call').get('call_index').replace('0x', ''),  # "0x4901"
                module_id=value.get('call').get('call_module'),
                call_id=value.get('call').get('call_function'),
                params=value.get('call').get('call_args'),
                spec_version_id=parent_spec_version,
                success=int(extrinsic_success),
                error=int(not extrinsic_success),
                codec_error=False
            )
            model.save(self.db_session)

            extrinsics.append(model)

            extrinsic_idx += 1

            # Process extrinsic
            if extrinsic.signed:
                block.count_extrinsics_signed += 1

                if model.signedby_address:
                    block.count_extrinsics_signedby_address += 1
                if model.signedby_index:
                    block.count_extrinsics_signedby_index += 1

                # Add search index for signed extrinsics
                search_index = SearchIndex(
                    index_type_id=settings.SEARCH_INDEX_SIGNED_EXTRINSIC,
                    block_id=block.id,
                    extrinsic_idx=model.extrinsic_idx,
                    account_id=model.address
                )
                search_index.save(self.db_session)

            else:
                block.count_extrinsics_unsigned += 1

            # Process extrinsic processors
            for processor_class in ProcessorRegistry().get_extrinsic_processors(model.module_id, model.call_id):
                print("RUN get_extrinsic_processors . ", model.module_id, model.call_id)
                extrinsic_processor = processor_class(block, model, substrate=self.substrate)
                extrinsic_processor.accumulation_hook(self.db_session)
                extrinsic_processor.process_search_index(self.db_session)

        # Process event processors
        for event in events:
            extrinsic = None
            if event.extrinsic_idx is not None:
                try:
                    extrinsic = extrinsics[event.extrinsic_idx]
                except IndexError:
                    extrinsic = None

            for processor_class in ProcessorRegistry().get_event_processors(event.module_id, event.event_id):
                event_processor = processor_class(block, event, extrinsic,
                                                  metadata=self.metadata_store.get(block.spec_version_id),
                                                  substrate=self.substrate)
                event_processor.accumulation_hook(self.db_session)
                event_processor.process_search_index(self.db_session)

        # Process block processors
        for processor_class in ProcessorRegistry().get_block_processors():
            block_processor = processor_class(block, substrate=self.substrate, harvester=self)
            block_processor.accumulation_hook(self.db_session)

        # Debug info
        if settings.DEBUG:
            block.debug_info = json_block

        # ==== Save data block ==================================

        block.save(self.db_session)

        return block

    def remove_block(self, block_hash):
        # Retrieve block
        block = Block.query(self.db_session).filter_by(hash=block_hash).first()

        print('remove-block: ', block.id)

        # Revert event processors
        for event in Event.query(self.db_session).filter_by(block_id=block.id):
            for processor_class in ProcessorRegistry().get_event_processors(event.module_id, event.event_id):
                event_processor = processor_class(block, event, None)
                event_processor.accumulation_revert(self.db_session)

        # Revert extrinsic processors
        for extrinsic in Extrinsic.query(self.db_session).filter_by(block_id=block.id):
            for processor_class in ProcessorRegistry().get_extrinsic_processors(extrinsic.module_id, extrinsic.call_id):
                extrinsic_processor = processor_class(block, extrinsic)
                extrinsic_processor.accumulation_revert(self.db_session)

        # Revert block processors
        for processor_class in ProcessorRegistry().get_block_processors():
            block_processor = processor_class(block)
            block_processor.accumulation_revert(self.db_session)

        # Delete events
        for item in Event.query(self.db_session).filter_by(block_id=block.id):
            print('remove-event: ', item)
            self.db_session.delete(item)
        # Delete extrinsics
        for item in Extrinsic.query(self.db_session).filter_by(block_id=block.id):
            print('remove-extrinsics: ', item)
            self.db_session.delete(item)

        # Delete block
        print('delete-block', block.id, block.hash)
        self.db_session.delete(block)
        self.db_session.commit()

    def debug_task(self):
        sequencer_task = Status.get_status(self.db_session, 'SEQUENCER_TASK_ID')
        print(sequencer_task.value, sequencer_task.last_modified)
        old_time_str = '2022-09-23 09:49:58'
        # old_time = datetime.strptime(old_time_str, "%Y-%m-%d %H:%M:%S")
        # status_time = datetime.strptime(sequencer_task.last_modified, "%Y-%m-%d %H:%M:%S")
        print(Status.diff_second(old_time_str))
        sequencer_task.value = '456'
        sequencer_task.last_modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sequencer_task.save(self.db_session)

    def sequence_block(self, block: Block, parent_block_data=None, parent_sequenced_block_data=None):
        print('RUN 0 Check BlockTotal')

        spec_version = block.spec_version_id
        if spec_version not in self.substrate.metadata_cache:
            self.substrate.init_runtime(block_hash=block.hash)

        total_treasury_burn = 0
        print('RUN 1 Check BlockTotal')
        if parent_sequenced_block_data:
            print('RUN 2 Check BlockTotal')
            total_treasury_burn = parent_sequenced_block_data.get('total_treasury_burn', 0)
        print('RUN 3 Check BlockTotal')

        # Remove old data before insert.
        for item in BlockTotal.query(self.db_session).filter_by(
                id=block.id):
            self.db_session.delete(item)

        sequenced_block = BlockTotal(
            id=block.id,
            total_treasury_burn=total_treasury_burn  # update by event processor
        )

        # Process block processors
        for processor_class in ProcessorRegistry().get_block_processors():
            block_processor = processor_class(block, sequenced_block, substrate=self.substrate)
            # Goto block sequencing_hook
            block_processor.sequencing_hook(
                self.db_session,
                parent_block_data,
                parent_sequenced_block_data
            )

        extrinsics = Extrinsic.query(self.db_session).filter_by(block_id=block.id).order_by('extrinsic_idx')

        for extrinsic in extrinsics:
            # Process extrinsic processors
            for processor_class in ProcessorRegistry().get_extrinsic_processors(extrinsic.module_id, extrinsic.call_id):
                extrinsic_processor = processor_class(block, extrinsic, substrate=self.substrate)
                extrinsic_processor.sequencing_hook(
                    self.db_session,
                    parent_block_data,
                    parent_sequenced_block_data
                )

        events = Event.query(self.db_session).filter_by(block_id=block.id).order_by('event_idx')

        # Process event processors
        for event in events:
            extrinsic = None
            if event.extrinsic_idx is not None:
                try:
                    extrinsic = extrinsics[event.extrinsic_idx]
                except IndexError:
                    extrinsic = None

            for processor_class in ProcessorRegistry().get_event_processors(event.module_id, event.event_id):
                event_processor = processor_class(block=block, event=event, extrinsic=extrinsic,
                                                  substrate=self.substrate, sequenced_block=sequenced_block)
                event_processor.sequencing_hook(
                    self.db_session,
                    parent_block_data,
                    parent_sequenced_block_data
                )

        sequenced_block.save(self.db_session)

        return sequenced_block

    def integrity_checks(self):

        # 1. Check finalized head
        if settings.FINALIZATION_BY_BLOCK_CONFIRMATIONS > 0:
            finalized_block_hash = self.substrate.get_chain_head()
            finalized_block_number = max(
                self.substrate.get_block_number(finalized_block_hash) - settings.FINALIZATION_BY_BLOCK_CONFIRMATIONS, 0
            )
        else:
            finalized_block_hash = self.substrate.get_chain_finalised_head()
            finalized_block_number = self.substrate.get_block_number(finalized_block_hash)

        # 2. Check integrity head
        integrity_head = Status.get_status(self.db_session, 'INTEGRITY_HEAD')

        if not integrity_head.value:
            # Only continue if block #1 exists
            if Block.query(self.db_session).filter_by(id=1).count() == 0:
                raise BlockIntegrityError('Chain not at genesis')

            integrity_head.value = 0
            integrity_head.last_modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            integrity_head.value = int(integrity_head.value)
            integrity_head.last_modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        start_block_id = max(integrity_head.value - 1, 0)
        end_block_id = finalized_block_number
        chunk_size = 1000
        parent_block = None

        if start_block_id < end_block_id:
            # Continue integrity check

            print('== Start integrity checks from {} to {} =='.format(start_block_id, end_block_id))

            for block_nr in range(start_block_id, end_block_id, chunk_size):
                # TODO replace limit with filter_by block range
                # block_range = Block.query(self.db_session).order_by('id')[block_nr:block_nr + chunk_size]
                block_range = Block.query(self.db_session).order_by('id').offset(block_nr).limit(chunk_size)
                for block in block_range:
                    if parent_block:
                        print('Kami-DEBUG block.id={}, parent_block.id={}'.format(block.id, parent_block.id))
                        if block.id != parent_block.id + 1:

                            check_block_hash = self.substrate.get_block_hash(integrity_head.value)
                            print('Kami-DEBUG integrity_checks: check_block_hash ={}, integrity_head.value={}'.format(
                                check_block_hash, integrity_head.value))
                            # Save integrity head if block hash of parent matches with hash in node
                            if parent_block.hash == check_block_hash:
                                integrity_head.save(self.db_session)
                                self.db_session.commit()

                            try:
                                re_add_hash = self.substrate.get_block_hash(parent_block.id + 1)
                                print('Kami Try Add={} AND hash={}'.format(parent_block.id + 1, re_add_hash))
                                for item in SymbolSnapshot.query(self.db_session).filter_by(
                                        block_id=parent_block.id + 1):
                                    print('Kami Delete SymbolSnapshot. ')
                                    self.db_session.delete(item)
                                self.add_block(re_add_hash)
                                self.db_session.commit()

                                integrity_head.value = parent_block.id - 1
                                integrity_head.save(self.db_session)
                                self.db_session.commit()

                            except Exception as e:
                                error_msg = 'Kami Block #{} is missing.. stopping check, {}, #{}, #{}'.format(
                                    parent_block.id + 1, check_block_hash, e.__class__, e.__context__)
                                print(error_msg)
                                raise BlockIntegrityError(error_msg)

                            # raise BlockIntegrityError(
                            #     'Kami Block #{} is missing.. stopping check '.format(parent_block.id + 1)
                            # )

                        elif block.parent_hash != parent_block.hash:

                            self.process_reorg_block(parent_block)
                            self.process_reorg_block(block)

                            self.remove_block(block.hash)
                            self.remove_block(parent_block.hash)
                            self.db_session.commit()

                            self.add_block(self.substrate.get_block_hash(block.id))
                            self.add_block(self.substrate.get_block_hash(parent_block.id))
                            self.db_session.commit()

                            integrity_head.value = parent_block.id - 1

                            # Save integrity head if block hash of parent matches with hash in node
                            # if parent_block.parent_hash == substrate.get_block_hash(integrity_head.value):
                            integrity_head.save(self.db_session)
                            self.db_session.commit()

                            print('Kami parent_hash != hash {}!={}'.format(block.parent_hash, parent_block.hash))

                            raise BlockIntegrityError(
                                'ERROR: Block #{} failed integrity checks, Re-adding #{}.. '.format(parent_block.id,
                                                                                                    block.id))
                        # else:
                        #     integrity_head.value = block.id

                    parent_block = block
                    integrity_head.value = block.id

                    if block.id == end_block_id:
                        break

                if integrity_head.value:
                    integrity_head.save(self.db_session)
                    self.db_session.commit()

            if parent_block:
                if parent_block.hash == self.substrate.get_block_hash(int(integrity_head.value)):
                    integrity_head.save(self.db_session)
                    self.db_session.commit()

        return {'integrity_head': integrity_head.value}

    def start_sequencer(self):
        print("RUN X start_sequencer start")
        try:
            self.integrity_checks()
            self.db_session.commit()

            block_nr = None

            integrity_head = Status.get_status(self.db_session, 'INTEGRITY_HEAD')

            if not integrity_head.value:
                integrity_head.value = 0

            # 3. Check sequence head
            sequencer_head = self.db_session.query(func.max(BlockTotal.id)).one()[0]

            if sequencer_head is None:
                sequencer_head = -1

            # Start sequencing process

            sequencer_parent_block = BlockTotal.query(self.db_session).filter_by(id=sequencer_head).first()
            parent_block = Block.query(self.db_session).filter_by(id=sequencer_head).first()

            print(f"Kami: sequencer range:{sequencer_head + 1} to {int(integrity_head.value) + 1}")
            for block_nr in range(sequencer_head + 1, int(integrity_head.value) + 1):

                if block_nr == 0:
                    # No block ever sequenced, check if chain is at genesis state
                    assert (not sequencer_parent_block)

                    block = Block.query(self.db_session).order_by('id').first()

                    if not block:
                        self.db_session.commit()
                        return {'error': 'Chain not at genesis'}

                    if block.id == 1:
                        # Add genesis block
                        block = self.add_block(block.parent_hash)

                    if block.id != 0:
                        self.db_session.commit()
                        return {'error': 'Chain not at genesis'}

                    self.process_genesis(block)

                    sequencer_parent_block_data = None
                    parent_block_data = None
                else:
                    block_id = sequencer_parent_block.id + 1

                    assert (block_id == block_nr)

                    block = Block.query(self.db_session).get(block_nr)

                    if not block:
                        self.db_session.commit()
                        return {'result': 'Finished at #{}'.format(sequencer_parent_block.id)}

                    sequencer_parent_block_data = sequencer_parent_block.asdict()
                    parent_block_data = parent_block.asdict()

                print(f"sequence_block {block.id} For data_block_total.")
                sequenced_block = self.sequence_block(block, parent_block_data, sequencer_parent_block_data)
                self.db_session.commit()

                parent_block = block
                sequencer_parent_block = sequenced_block

            if block_nr is None:
                return {'result': 'Finished at #{}'.format(block_nr)}
            else:
                return {'result': 'Nothing to sequence'}
        except Exception as e:
            return {'result': 'start_sequencer had an error {}'.format(
                traceback.format_exception(type(e), e, e.__traceback__))}

    def process_reorg_block(self, block):

        # Check if reorg already exists
        if ReorgBlock.query(self.db_session).filter_by(hash=block.hash).count() == 0:

            model = ReorgBlock(**block.asdict())
            model.save(self.db_session)

            for extrinsic in Extrinsic.query(self.db_session).filter_by(block_id=block.id):
                model = ReorgExtrinsic(block_hash=block.hash, **extrinsic.asdict())
                model.save(self.db_session)

            for event in Event.query(self.db_session).filter_by(block_id=block.id):
                model = ReorgEvent(block_hash=block.hash, **event.asdict())
                model.save(self.db_session)

            for log in Log.query(self.db_session).filter_by(block_id=block.id):
                model = ReorgLog(block_hash=block.hash, **log.asdict())
                model.save(self.db_session)

    def rebuild_search_index(self):

        self.db_session.execute('truncate table {}'.format(SearchIndex.__tablename__))

        for block in Block.query(self.db_session).order_by('id').yield_per(1000):

            extrinsic_lookup = {}
            block._accounts_new = []
            block._accounts_reaped = []

            for extrinsic in Extrinsic.query(self.db_session).filter_by(block_id=block.id).order_by('extrinsic_idx'):
                extrinsic_lookup[extrinsic.extrinsic_idx] = extrinsic

                # Add search index for signed extrinsics
                if extrinsic.address:
                    search_index = SearchIndex(
                        index_type_id=settings.SEARCH_INDEX_SIGNED_EXTRINSIC,
                        block_id=block.id,
                        extrinsic_idx=extrinsic.extrinsic_idx,
                        account_id=extrinsic.address
                    )
                    search_index.save(self.db_session)

                # Process extrinsic processors
                for processor_class in ProcessorRegistry().get_extrinsic_processors(extrinsic.module_id,
                                                                                    extrinsic.call_id):
                    extrinsic_processor = processor_class(block=block, extrinsic=extrinsic, substrate=self.substrate)
                    extrinsic_processor.process_search_index(self.db_session)

            for event in Event.query(self.db_session).filter_by(block_id=block.id).order_by('event_idx'):
                extrinsic = None
                if event.extrinsic_idx is not None:
                    try:
                        extrinsic = extrinsic_lookup[event.extrinsic_idx]
                    except (IndexError, KeyError):
                        extrinsic = None

                for processor_class in ProcessorRegistry().get_event_processors(event.module_id, event.event_id):
                    event_processor = processor_class(block, event, extrinsic,
                                                      metadata=self.metadata_store.get(block.spec_version_id),
                                                      substrate=self.substrate)
                    event_processor.process_search_index(self.db_session)

            self.db_session.commit()

    def create_full_balance_snaphot(self, block_id):

        block_hash = self.substrate.get_block_hash(block_id)

        # Determine if keys have Blake2_128Concat format so AccountId is stored in storage key
        storage_method = self.substrate.get_metadata_storage_function(
            module_name="System",
            storage_name="Account",
            block_hash=block_hash
        )

        if storage_method:
            if storage_method.type['Map']['hasher'] == "Blake2_128Concat":

                # get balances storage prefix
                storage_key_prefix = self.substrate.generate_storage_hash(
                    storage_module='System',
                    storage_function='Account'
                )

                rpc_result = self.substrate.rpc_request(
                    'state_getKeys',
                    [storage_key_prefix, block_hash]
                ).get('result')
                # Extract accounts from storage key
                accounts = [storage_key[-64:] for storage_key in rpc_result if len(storage_key) == 162]
            else:
                # Retrieve accounts from database for legacy blocks
                accounts = [account[0] for account in self.db_session.query(distinct(Account.id))]

            for account_id in accounts:
                self.create_balance_snapshot(block_id=block_id, account_id=account_id, block_hash=block_hash)

    def create_balance_snapshot(self, block_id, account_id, block_hash=None):

        if not block_hash:
            block_hash = self.substrate.get_block_hash(block_id)

        # Get balance for account
        try:
            account_info_data = self.substrate.get_runtime_state(
                module='System',
                storage_function='Account',
                params=['0x{}'.format(account_id)],
                block_hash=block_hash
            ).get('result')

            # Make sure no rows inserted before processing this record
            AccountInfoSnapshot.query(self.db_session).filter_by(block_id=block_id, account_id=account_id).delete()

            if account_info_data:
                account_info_obj = AccountInfoSnapshot(
                    block_id=block_id,
                    account_id=account_id,
                    account_info=account_info_data,
                    balance_free=account_info_data["data"]["free"],
                    balance_reserved=account_info_data["data"]["reserved"],
                    balance_total=account_info_data["data"]["free"] + account_info_data["data"]["reserved"],
                    nonce=account_info_data["nonce"]
                )
            else:
                account_info_obj = AccountInfoSnapshot(
                    block_id=block_id,
                    account_id=account_id,
                    account_info=None,
                    balance_free=None,
                    balance_reserved=None,
                    balance_total=None,
                    nonce=None
                )

            account_info_obj.save(self.db_session)
        except ValueError:
            pass

    def update_account_balances(self):
        # set balances according to most recent snapshot
        account_info = self.db_session.execute("""
                        select
                           a.account_id, 
                           a.balance_total,
                           a.balance_free,
                           a.balance_reserved,
                           a.nonce
                    from
                         data_account_info_snapshot as a
                    inner join (
                        select 
                            account_id, max(block_id) as max_block_id 
                        from data_account_info_snapshot 
                        group by account_id
                    ) as b
                    on a.account_id = b.account_id and a.block_id = b.max_block_id
                    """)

        for account_id, balance_total, balance_free, balance_reserved, nonce in account_info:
            Account.query(self.db_session).filter_by(id=account_id).update(
                {
                    Account.balance_total: balance_total,
                    Account.balance_free: balance_free,
                    Account.balance_reserved: balance_reserved,
                    Account.nonce: nonce,
                }, synchronize_session='fetch'
            )
