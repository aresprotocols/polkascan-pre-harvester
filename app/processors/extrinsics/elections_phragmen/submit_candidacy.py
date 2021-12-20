from app.processors import ExtrinsicProcessor
from app.settings import SEARCH_INDEX_COUNCIL_CANDIDACY_SUBMIT


class ElectionsSubmitCandidacy(ExtrinsicProcessor):
    module_id = 'Elections'
    call_id = 'submit_candidacy'

    def process_search_index(self, db_session):
        if self.extrinsic.success:
            search_index = self.add_search_index(
                index_type_id=SEARCH_INDEX_COUNCIL_CANDIDACY_SUBMIT,
                account_id=self.extrinsic.address
            )

            search_index.save(db_session)
