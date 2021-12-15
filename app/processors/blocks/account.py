import binascii

from scalecodec.types import ss58_encode
from sqlalchemy.orm.exc import NoResultFound
from substrateinterface.utils.hasher import blake2_256

from app.models.data import AccountAudit, Account, SearchIndex, AccountIndex
from app.processors.base import BlockProcessor
from app.settings import ACCOUNT_AUDIT_TYPE_REAPED, ACCOUNT_AUDIT_TYPE_NEW, SUBSTRATE_ADDRESS_TYPE


class AccountBlockProcessor(BlockProcessor):

    def accumulation_hook(self, db_session):
        self.block.count_accounts_new += len(set(self.block._accounts_new))
        self.block.count_accounts_reaped += len(set(self.block._accounts_reaped))

        self.block.count_accounts = self.block.count_accounts_new - self.block.count_accounts_reaped

    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):

        for account_audit in AccountAudit.query(db_session).filter_by(block_id=self.block.id).order_by('event_idx'):
            try:
                account = Account.query(db_session).filter_by(id=account_audit.account_id).one()

                if account_audit.type_id == ACCOUNT_AUDIT_TYPE_REAPED:
                    account.count_reaped += 1
                    account.is_reaped = True

                elif account_audit.type_id == ACCOUNT_AUDIT_TYPE_NEW:
                    account.is_reaped = False

                account.updated_at_block = self.block.id

            except NoResultFound:

                account = Account(
                    id=account_audit.account_id,
                    address=ss58_encode(account_audit.account_id, SUBSTRATE_ADDRESS_TYPE),
                    hash_blake2b=blake2_256(binascii.unhexlify(account_audit.account_id)),
                    is_treasury=(account_audit.data or {}).get('is_treasury', False),
                    is_sudo=(account_audit.data or {}).get('is_sudo', False),
                    was_sudo=(account_audit.data or {}).get('is_sudo', False),
                    created_at_block=self.block.id,
                    updated_at_block=self.block.id
                )

                # Retrieve index in corresponding account
                account_index = AccountIndex.query(db_session).filter_by(account_id=account.id).first()

                if account_index:
                    account.index_address = account_index.short_address

                # Retrieve and set initial balance
                try:
                    account_info_data = self.substrate.get_runtime_state(
                        module='System',
                        storage_function='Account',
                        params=['0x{}'.format(account.id)],
                        block_hash=self.block.hash
                    ).get('result')

                    if account_info_data:
                        account.balance_free = account_info_data["data"]["free"]
                        account.balance_reserved = account_info_data["data"]["reserved"]
                        account.balance_total = account_info_data["data"]["free"] + account_info_data["data"][
                            "reserved"]
                        account.nonce = account_info_data["nonce"]
                except ValueError as e:
                    print("ValueError: {}".format(e))
                    pass

                # # If reaped but does not exist, create new account for now
                # if account_audit.type_id != ACCOUNT_AUDIT_TYPE_NEW:
                #     account.is_reaped = True
                #     account.count_reaped = 1

            account.save(db_session)

        # Until SUDO and batch calls are processed separately we need to do a safety check to be sure we include all
        # accounts that have activity (lookup in account_index) in current block
        # TODO implement calls

        for search_index in db_session.query(SearchIndex.account_id).filter(
                SearchIndex.block_id == self.block.id,
                SearchIndex.account_id.notin_(db_session.query(Account.id))
        ).distinct():

            account = Account(
                id=search_index.account_id,
                address=ss58_encode(search_index.account_id, SUBSTRATE_ADDRESS_TYPE),
                hash_blake2b=blake2_256(binascii.unhexlify(search_index.account_id)),
                created_at_block=self.block.id,
                updated_at_block=self.block.id
            )

            try:
                account_info_data = self.substrate.get_runtime_state(
                    module='System',
                    storage_function='Account',
                    params=['0x{}'.format(account.id)],
                    block_hash=self.block.hash
                ).get('result')

                if account_info_data:
                    account.balance_free = account_info_data["data"]["free"]
                    account.balance_reserved = account_info_data["data"]["reserved"]
                    account.balance_total = account_info_data["data"]["free"] + account_info_data["data"]["reserved"]
                    account.nonce = account_info_data["nonce"]
            except ValueError:
                pass

            account.save(db_session)
