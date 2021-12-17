from app.processors import ExtrinsicProcessor
from app.settings import SEARCH_INDEX_STAKING_NOMINATE


class StakingNominate(ExtrinsicProcessor):
    module_id = 'Staking'
    call_id = 'nominate'

    def process_search_index(self, db_session):
        if self.extrinsic.success:
            search_index = self.add_search_index(
                index_type_id=SEARCH_INDEX_STAKING_NOMINATE,
                account_id=self.extrinsic.address
            )

            search_index.save(db_session)
