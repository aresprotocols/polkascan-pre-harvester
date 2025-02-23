from app.processors.base import EventProcessor
from app.settings import SEARCH_INDEX_HEARTBEATRECEIVED


class HeartbeatReceivedEventProcessor(EventProcessor):
    module_id = 'imonline'
    event_id = 'HeartbeatReceived'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=SEARCH_INDEX_HEARTBEATRECEIVED,
            account_id=self.event.attributes[0]['value'].replace('0x', ''),
            sorting_value=None
        )

        search_index.save(db_session)
