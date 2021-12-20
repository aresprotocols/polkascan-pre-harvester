from app.processors import ExtrinsicProcessor
from app.settings import SEARCH_INDEX_COUNCIL_CANDIDACY_VOTE


class ElectionsVote(ExtrinsicProcessor):
    module_id = 'Elections'
    call_id = 'vote'

    def process_search_index(self, db_session):

        if self.extrinsic.success:
            search_index = self.add_search_index(
                index_type_id=SEARCH_INDEX_COUNCIL_CANDIDACY_VOTE,
                account_id=self.extrinsic.address,
                sorting_value=self.extrinsic.params[1]['value']
            )

            search_index.save(db_session)

            # Reverse lookup
            for candidate in self.extrinsic.params[0]['value']:
                search_index = self.add_search_index(
                    index_type_id=SEARCH_INDEX_COUNCIL_CANDIDACY_VOTE,
                    account_id=candidate.replace('0x', ''),
                    sorting_value=self.extrinsic.params[1]['value']
                )

                search_index.save(db_session)
