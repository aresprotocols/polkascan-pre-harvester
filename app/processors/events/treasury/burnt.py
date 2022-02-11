from app.processors import EventProcessor
from app.settings import SEARCH_INDEX_TREASURY_AWARDED


class TreasuryBurnt(EventProcessor):
    module_id = 'Treasury'
    event_id = 'Burnt'

    def sequencing_hook(self, db_session, parent_block, parent_sequenced_block):
        if not parent_sequenced_block:
            parent_sequenced_block = {}
        if self.sequenced_block:
            self.sequenced_block.total_treasury_burn = int(parent_sequenced_block.get('total_treasury_burn', 0)) + \
                                                       self.event.attributes[0]['value']
