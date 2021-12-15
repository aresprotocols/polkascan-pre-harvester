from app.processors.base import EventProcessor
from app.settings import SEARCH_INDEX_BALANCETRANSFER


class BalancesTransferProcessor(EventProcessor):
    module_id = 'Balances'
    event_id = 'Transfer'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=SEARCH_INDEX_BALANCETRANSFER,
            account_id=self.event.attributes[0]['value'].replace('0x', ''),
            sorting_value=self.event.attributes[2]['value']
        )

        search_index.save(db_session)

        search_index = self.add_search_index(
            index_type_id=SEARCH_INDEX_BALANCETRANSFER,
            account_id=self.event.attributes[1]['value'].replace('0x', ''),
            sorting_value=self.event.attributes[2]['value']
        )

        search_index.save(db_session)
