from app.processors import EventProcessor
from app.settings import SEARCH_INDEX_TREASURY_AWARDED


class TreasuryAwarded(EventProcessor):
    module_id = 'Treasury'
    event_id = 'awarded'

    def process_search_index(self, db_session):
        # Add Beneficiary
        search_index = self.add_search_index(
            index_type_id=SEARCH_INDEX_TREASURY_AWARDED,
            account_id=self.event.attributes[2]['value'].replace('0x', ''),
            sorting_value=self.event.attributes[1]['value']
        )

        search_index.save(db_session)
