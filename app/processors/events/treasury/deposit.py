from app.processors import EventProcessor
from app.settings import SEARCH_INDEX_TREASURY_DEPOSIT, SUBSTRATE_TREASURY_ACCOUNTS


class TreasuryProposed(EventProcessor):
    module_id = 'Treasury'
    event_id = 'Deposit'

    def process_search_index(self, db_session):
        for account_id in SUBSTRATE_TREASURY_ACCOUNTS:
            search_index = self.add_search_index(
                index_type_id=SEARCH_INDEX_TREASURY_DEPOSIT,
                account_id=account_id,
                sorting_value=self.event.attributes[0]['value']
            )
            search_index.save(db_session)
