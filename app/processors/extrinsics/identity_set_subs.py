from app.processors import ExtrinsicProcessor
from app.settings import SEARCH_INDEX_IDENTITY_SET_SUBS


class IdentitySetSubsExtrinsicProcessor(ExtrinsicProcessor):
    module_id = 'Identity'
    call_id = 'set_subs'

    def process_search_index(self, db_session):
        if self.extrinsic.success:
            search_index = self.add_search_index(
                index_type_id=SEARCH_INDEX_IDENTITY_SET_SUBS,
                account_id=self.extrinsic.address
            )

            search_index.save(db_session)
