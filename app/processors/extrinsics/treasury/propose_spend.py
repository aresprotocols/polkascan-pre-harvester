from app.processors import ExtrinsicProcessor
from app.settings import SEARCH_INDEX_TREASURY_PROPOSED


class TreasuryProposeSpend(ExtrinsicProcessor):
    module_id = 'Treasury'
    call_id = 'propose_spend'

    def process_search_index(self, db_session):
        if self.extrinsic.success:
            search_index = self.add_search_index(
                index_type_id=SEARCH_INDEX_TREASURY_PROPOSED,
                account_id=self.extrinsic.address,
                sorting_value=self.extrinsic.params[0]['value']
            )

            search_index.save(db_session)

            # Add Beneficiary

            # search_index = self.add_search_index(
            #     index_type_id=SEARCH_INDEX_TREASURY_PROPOSED,
            #     account_id=self.extrinsic.params[1]['value'].replace('0x', ''),
            #     sorting_value=self.extrinsic.params[0]['value']
            # )
            #
            # search_index.save(db_session)
