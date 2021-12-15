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


class NewAccountEventProcessor(EventProcessor):
    """
        unuseful
        new_version use SystemNewAccountEventProcessor instead of
    """
    module_id = 'Balances'
    event_id = 'NewAccount'

    def accumulation_hook(self, db_session):
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


class ReapedAccount(EventProcessor):
    """
        unuseful
    """
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
