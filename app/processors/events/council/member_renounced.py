from app.processors.base import EventProcessor
from app.settings import SEARCH_INDEX_COUNCIL_CANDIDACY_RENOUNCED


class CouncilMemberRenounced(EventProcessor):
    module_id = 'electionsphragmen'
    event_id = 'MemberRenounced'

    def process_search_index(self, db_session):
        search_index = self.add_search_index(
            index_type_id=SEARCH_INDEX_COUNCIL_CANDIDACY_RENOUNCED,
            account_id=self.event.attributes[0]['value'].replace('0x', '')
        )

        search_index.save(db_session)
