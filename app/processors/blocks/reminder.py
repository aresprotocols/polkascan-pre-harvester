import binascii

from scalecodec.types import ss58_encode
from sqlalchemy.orm.exc import NoResultFound
from substrateinterface.utils.hasher import blake2_256
from app import utils
from app.models.data import AccountAudit, Account, SearchIndex, AccountIndex, DataReminder
from app.processors.base import BlockProcessor
from app.settings import ACCOUNT_AUDIT_TYPE_REAPED, ACCOUNT_AUDIT_TYPE_NEW, SUBSTRATE_ADDRESS_TYPE


class ReminderProcessor(BlockProcessor):

    def accumulation_hook(self, db_session):
        print('### ReminderProcessor:accumulation_hook....', self.block.id)

    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):
        print('### ReminderProcessor:sequencing_hook....', self.block.id)
        # audits = DataReminder.query(db_session).filter_by(block_id=self.block.id).order_by('event_idx')
        # for identity_audit in audits:

    # def aggregation_hook(self, db_session):
    #     print('### ReminderProcessor ### {}-{}'.format(self.block.id, self.sequenced_block))
