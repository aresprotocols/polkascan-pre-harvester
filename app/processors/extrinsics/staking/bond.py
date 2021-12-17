from app.processors import ExtrinsicProcessor
from app.settings import SEARCH_INDEX_STAKING_BONDED


class StakingBond(ExtrinsicProcessor):
    module_id = 'Staking'
    call_id = 'bond'

    def process_search_index(self, db_session):
        if self.extrinsic.success:
            search_index = self.add_search_index(
                index_type_id=SEARCH_INDEX_STAKING_BONDED,
                account_id=self.extrinsic.address,
                sorting_value=self.extrinsic.params[1]['value']
            )

            search_index.save(db_session)
