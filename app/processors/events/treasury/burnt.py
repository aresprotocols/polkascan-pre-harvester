from app.models.data import Event
from app.processors import EventProcessor
from app.settings import SEARCH_INDEX_TREASURY_AWARDED


class TreasuryBurnt(EventProcessor):
    module_id = 'Treasury'
    event_id = 'Burnt'

    def sequencing_hook(self, db_session, parent_block, parent_sequenced_block):
        if not parent_sequenced_block:
            parent_sequenced_block = {}
        total_treasury_burn = parent_sequenced_block.get('total_treasury_burn', 0)
        if total_treasury_burn == 0:
            burns = db_session.query(Event).filter_by(module_id=self.module_id, event_id=self.event_id).all()
            for _, burn in enumerate(burns):
                value = burn.attributes[0]['value']
                total_treasury_burn += value
        if self.sequenced_block:
            self.sequenced_block.total_treasury_burn = int(total_treasury_burn) + self.event.attributes[0]['value']
