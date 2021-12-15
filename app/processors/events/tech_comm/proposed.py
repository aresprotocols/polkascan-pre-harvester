from app.processors.base import EventProcessor
from app.settings import SEARCH_INDEX_TECHCOMM_PROPOSED


class TechCommProposedEventProcessor(EventProcessor):
    module_id = 'Technicalcommittee'
    event_id = 'Proposed'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=SEARCH_INDEX_TECHCOMM_PROPOSED,
            account_id=self.extrinsic.address
        )

        search_index.save(db_session)
