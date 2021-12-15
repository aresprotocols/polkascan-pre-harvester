from app.models.data import AccountIndexAudit
from app.processors.base import EventProcessor
from app.settings import ACCOUNT_INDEX_AUDIT_TYPE_NEW


class NewAccountIndexEventProcessor(EventProcessor):
    module_id = 'Indices'
    event_id = 'NewAccountIndex'

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
