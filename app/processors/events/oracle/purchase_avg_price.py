from app.models.data import PriceRequest
from app.processors import EventProcessor


class PurchasedAvgPriceEventProcessor(EventProcessor):
    module_id = 'AresOracle'
    event_id = 'PurchasedAvgPrice'

    def accumulation_hook(self, db_session):
        attributes = self.event.attributes
        purchase_id = attributes[0]['value']
        data = attributes[1]['value']
        price_request: PriceRequest = PriceRequest.query(db_session).filter_by(order_id=purchase_id).first()
        if price_request:
            price_request.ended_at = self.block.id
        else:
            price_request: PriceRequest = PriceRequest(
                order_id=purchase_id,
                ended_at=self.block.id
            )
        result = {}
        auth = {}
        for symbol_result in data:
            symbol = symbol_result[0]
            price_data = symbol_result[1]
            result[symbol] = {"reached_type": price_data['reached_type'], 'price_data': price_data['price_data']}
            auth[symbol] = symbol_result[2]
        price_request.result = result
        price_request.auth = auth
        price_request.save(db_session)
