from app.processors.base import EventProcessor
from app.settings import SEARCH_INDEX_STAKING_WITHDRAWN


class StakingWithdrawn(EventProcessor):
    module_id = 'staking'
    event_id = 'Withdrawn'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=SEARCH_INDEX_STAKING_WITHDRAWN,
            account_id=self.event.attributes[0].replace('0x', ''),
            sorting_value=self.event.attributes[1]
        )

        search_index.save(db_session)
