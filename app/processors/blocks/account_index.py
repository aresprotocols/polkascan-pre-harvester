from app.models.data import AccountIndexAudit, AccountIndex, Account
from app.processors import BlockProcessor
from app.settings import ACCOUNT_INDEX_AUDIT_TYPE_NEW, SUBSTRATE_ADDRESS_TYPE, ACCOUNT_INDEX_AUDIT_TYPE_REAPED
from app.utils.ss58 import ss58_encode_account_index


class AccountIndexBlockProcessor(BlockProcessor):

    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):

        for account_index_audit in AccountIndexAudit.query(db_session).filter_by(
                block_id=self.block.id
        ).order_by('event_idx'):

            if account_index_audit.type_id == ACCOUNT_INDEX_AUDIT_TYPE_NEW:

                # Check if account index already exists
                account_index = AccountIndex.query(db_session).filter_by(
                    id=account_index_audit.account_index_id
                ).first()

                if not account_index:
                    account_index = AccountIndex(
                        id=account_index_audit.account_index_id,
                        created_at_block=self.block.id
                    )

                account_index.account_id = account_index_audit.account_id
                account_index.short_address = ss58_encode_account_index(
                    account_index_audit.account_index_id,
                    SUBSTRATE_ADDRESS_TYPE
                )
                account_index.updated_at_block = self.block.id

                account_index.save(db_session)

                # Update index in corresponding account
                account = Account.query(db_session).get(account_index.account_id)

                if account:
                    account.index_address = account_index.short_address
                    account.save(db_session)

            elif account_index_audit.type_id == ACCOUNT_INDEX_AUDIT_TYPE_REAPED:

                if account_index_audit.account_index_id:
                    account_index_list = AccountIndex.query(db_session).filter_by(
                        id=account_index_audit.account_index_id
                    )
                else:
                    account_index_list = AccountIndex.query(db_session).filter_by(
                        account_id=account_index_audit.account_id
                    )

                for account_index in account_index_list:
                    account_index.account_id = None
                    account_index.is_reclaimable = True
                    account_index.updated_at_block = self.block.id
                    account_index.save(db_session)
