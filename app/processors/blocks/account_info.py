from sqlalchemy import distinct

from app.models.data import SearchIndex, AccountInfoSnapshot, Account
from app.processors import BlockProcessor
from app.settings import BALANCE_FULL_SNAPSHOT_INTERVAL, CELERY_RUNNING


class AccountInfoBlockProcessor(BlockProcessor):

    def accumulation_hook(self, db_session):
        # Store in AccountInfoSnapshot for all processed search indices and per 10000 blocks

        if self.block.id % BALANCE_FULL_SNAPSHOT_INTERVAL == 0:
            from app.tasks import update_balances_in_block

            if CELERY_RUNNING:
                update_balances_in_block.delay(self.block.id)
            else:
                update_balances_in_block(self.block.id)
        else:
            # Retrieve unique accounts in all searchindex records for current block
            for search_index in db_session.query(distinct(SearchIndex.account_id)).filter_by(block_id=self.block.id):
                self.harvester.create_balance_snapshot(
                    block_id=self.block.id,
                    block_hash=self.block.hash,
                    account_id=search_index[0]
                )

    def sequencing_hook(self, db_session, parent_block, parent_sequenced_block):
        # Update Account according to AccountInfoSnapshot

        for account_info in AccountInfoSnapshot.query(db_session).filter_by(block_id=self.block.id):
            account = Account.query(db_session).get(account_info.account_id)
            if account:
                account.balance_total = account_info.balance_total
                account.balance_reserved = account_info.balance_reserved
                account.balance_free = account_info.balance_free
                account.nonce = account_info.nonce
                account.save(db_session)
