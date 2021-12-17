from app.processors import ExtrinsicProcessor
from app.settings import SEARCH_INDEX_DEMOCRACY_VOTE


class DemocracyVoteExtrinsicProcessor(ExtrinsicProcessor):
    module_id = 'Democracy'
    call_id = 'vote'

    def process_search_index(self, db_session):

        if self.extrinsic.success:

            sorting_value = None

            # Try to retrieve balance of vote
            if self.extrinsic.params[1]['type'] == 'AccountVote<BalanceOf>':
                if 'Standard' in self.extrinsic.params[1]['value']:
                    sorting_value = self.extrinsic.params[1]['value']['Standard']['balance']

            search_index = self.add_search_index(
                index_type_id=SEARCH_INDEX_DEMOCRACY_VOTE,
                account_id=self.extrinsic.address,
                sorting_value=sorting_value
            )

            search_index.save(db_session)
