from app.processors import ExtrinsicProcessor
from app.settings import SEARCH_INDEX_DEMOCRACY_PROXY_VOTE


class DemocracyProxyVote(ExtrinsicProcessor):
    module_id = 'Democracy'
    call_id = 'proxy_vote'

    def process_search_index(self, db_session):
        if self.extrinsic.success:
            search_index = self.add_search_index(
                index_type_id=SEARCH_INDEX_DEMOCRACY_PROXY_VOTE,
                account_id=self.extrinsic.address
            )

            search_index.save(db_session)
