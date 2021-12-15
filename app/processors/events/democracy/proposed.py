from app.processors.base import EventProcessor
from app.settings import SEARCH_INDEX_DEMOCRACY_PROPOSE


class ProposedEventProcessor(EventProcessor):
    module_id = 'Democracy'
    event_id = 'Proposed'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=SEARCH_INDEX_DEMOCRACY_PROPOSE,
            account_id=self.extrinsic.address,
            sorting_value=self.extrinsic.params[1]['value']
        )

        search_index.save(db_session)
