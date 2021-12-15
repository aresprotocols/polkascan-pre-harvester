from app.processors.base import EventProcessor
from app.settings import SEARCH_INDEX_IMONLINE_SOMEOFFLINE


class SomeOffline(EventProcessor):
    module_id = 'imonline'
    event_id = 'SomeOffline'

    def process_search_index(self, db_session):
        for item in self.event.attributes[0]['value']:
            search_index = self.add_search_index(
                index_type_id=SEARCH_INDEX_IMONLINE_SOMEOFFLINE,
                account_id=item['validatorId'].replace('0x', ''),
                sorting_value=None
            )

            search_index.save(db_session)
