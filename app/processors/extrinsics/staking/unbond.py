from app.processors import ExtrinsicProcessor
from app.settings import SEARCH_INDEX_STAKING_UNBONDED


class StakingUnbond(ExtrinsicProcessor):
    module_id = 'Staking'
    call_id = 'unbond'

    def process_search_index(self, db_session):
        if self.extrinsic.success:
            search_index = self.add_search_index(
                index_type_id=SEARCH_INDEX_STAKING_UNBONDED,
                account_id=self.extrinsic.address,
                sorting_value=self.extrinsic.params[0]['value']
            )

            search_index.save(db_session)
