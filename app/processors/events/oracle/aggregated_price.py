from app.models.data import SymbolSnapshot
from app.processors import EventProcessor


class AggregatedPriceEventProcessor(EventProcessor):
    module_id = 'AresOracle'
    event_id = 'AggregatedPrice'

    def accumulation_hook(self, db_session):
        prices = self.event.attributes[0]['value']
        if self.block.id == 732801:
            return
        for price in prices:
            snapshot = SymbolSnapshot(
                block_id=self.block.id,
                symbol=price[0],
                price=price[1],
                fraction=price[2],
                auth=price[3],
                created_at=self.block.datetime
            )
            snapshot.save(db_session)
