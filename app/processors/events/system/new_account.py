from app import settings
from app.models.data import AccountAudit
from app.processors.base import EventProcessor
from app.settings import ACCOUNT_AUDIT_TYPE_NEW


class SystemNewAccountEventProcessor(EventProcessor):
    module_id = 'System'
    event_id = 'NewAccount'

    def accumulation_hook(self, db_session):
        # Check event requirements
        if len(self.event.attributes) == 1 and \
                (self.event.attributes[0]['type'] == 'AccountId' or self.event.attributes[0]['type'] == 'T::AccountId'):
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
            account_id=self.event.attributes[0]['value'].replace('0x', '')
        )

        search_index.save(db_session)
