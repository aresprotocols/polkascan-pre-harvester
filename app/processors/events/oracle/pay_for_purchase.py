from app.models.data import PriceRequest
from app.processors import EventProcessor


class PayForPurchaseEventProcessor(EventProcessor):
    module_id = 'OracleFinance'
    event_id = 'PayForPurchase'

    def accumulation_hook(self, db_session):
        attributes = self.event.attributes
        purchase_id = attributes[3]['value']
        fee = attributes[2]['value']
        price_request: PriceRequest = PriceRequest.query(db_session).filter_by(order_id=purchase_id).first()
        if price_request:
            price_request.payment = fee
            price_request.status = 1
            price_request.save(db_session)
        else:
            print("price_request not exist skip this event")
