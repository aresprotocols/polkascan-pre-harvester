from app.processors import ExtrinsicProcessor
from app.settings import SEARCH_INDEX_DEMOCRACY_SECOND


class DemocracySecond(ExtrinsicProcessor):
    module_id = 'Democracy'
    call_id = 'second'

    def process_search_index(self, db_session):
        if self.extrinsic.success:
            search_index = self.add_search_index(
                index_type_id=SEARCH_INDEX_DEMOCRACY_SECOND,
                account_id=self.extrinsic.address
            )

            search_index.save(db_session)
