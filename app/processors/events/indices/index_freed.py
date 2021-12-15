from app.processors.base import EventProcessor
from app.settings import ACCOUNT_INDEX_AUDIT_TYPE_REAPED
from app.models.data import AccountIndexAudit


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
