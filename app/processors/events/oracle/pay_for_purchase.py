from app.models.data import PriceRequest
from app.processors import EventProcessor


class PayForPurchaseEventProcessor(EventProcessor):
    module_id = 'OracleFinance'
    event_id = 'PayForPurchase'

    def accumulation_hook(self, db_session):
        attributes = self.event.attributes
        purchase_id = attributes[3]['value']

        if purchase_id['String']:
            purchase_id = purchase_id['String']

        fee = attributes[2]['value']
        price_request: PriceRequest = PriceRequest.query(db_session).filter_by(order_id=purchase_id).first()
        if price_request:
            price_request.payment = fee
            price_request.status = 1
        else:
            price_request: PriceRequest = PriceRequest(
                order_id=purchase_id,
                payment=fee,
                status=1,  # 0: pending,  1: successful, 2: failed
            )
        price_request.save(db_session)
