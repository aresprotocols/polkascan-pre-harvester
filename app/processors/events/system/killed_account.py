from app.models.data import AccountAudit
from app.processors.base import EventProcessor
from app.settings import ACCOUNT_AUDIT_TYPE_REAPED, SEARCH_INDEX_ACCOUNT_KILLED


class KilledAccount(EventProcessor):
    module_id = 'System'
    event_id = 'KilledAccount'

    def accumulation_hook(self, db_session):
        print("KilledAccount")
        print(self.event.attributes)
        # Check event requirements
        if len(self.event.attributes) == 1 and \
                (self.event.attributes[0]['type'] == 'T::AccountId' or self.event.attributes[0]['type'] == 'AccountId'):

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
            index_type_id=SEARCH_INDEX_ACCOUNT_KILLED,
            account_id=self.event.attributes[0]['value'].replace('0x', '')
        )

        search_index.save(db_session)
