from app.processors.base import EventProcessor
from app.settings import SEARCH_INDEX_SLASHED_ACCOUNT


class SlashEventProcessor(EventProcessor):
    module_id = 'Staking'
    event_id = 'Slash'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=SEARCH_INDEX_SLASHED_ACCOUNT,
            account_id=self.event.attributes[0]['value'].replace('0x', ''),
            sorting_value=self.event.attributes[1]['value']
        )

        search_index.save(db_session)
