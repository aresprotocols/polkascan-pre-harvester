from app.processors import EventProcessor
from app.settings import SEARCH_INDEX_TREASURY_DEPOSIT, SUBSTRATE_TREASURY_ACCOUNTS


class TreasuryProposed(EventProcessor):
    module_id = 'Treasury'
    event_id = 'deposit'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=SEARCH_INDEX_TREASURY_DEPOSIT,
            account_id=SUBSTRATE_TREASURY_ACCOUNTS,
            sorting_value=self.event.attributes[0]['value']
        )

        search_index.save(db_session)
