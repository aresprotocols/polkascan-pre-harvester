from app.models.data import EraPriceRequest, PriceRequest
from app.processors import EventProcessor


class NewPurchaseRequestEventProcessor(EventProcessor):
    module_id = 'AresOracle'
    event_id = 'NewPurchasedRequest'

    def accumulation_hook(self, db_session):
        attributes = self.event.attributes
        purchase_id = attributes[0]['value']
        fee = attributes[2]['value']
        era = attributes[3]['value']
        era_price_request: EraPriceRequest = EraPriceRequest.query(db_session).filter_by(era=era).first()

        # exist
        if era_price_request:
            era_price_request.era_total_requests += 1
            era_price_request.save(db_session)
        else:
            previous: EraPriceRequest = EraPriceRequest.query(db_session).filter_by(era=era - 1).first()
            era_price_request = EraPriceRequest(
                era=era,
                total_eras=previous.total_eras + 1 if previous else 0,
                era_total_requests=1,
                era_total_points=0,
                era_total_fee=0
            )
            era_price_request.save(db_session)

        request_data = attributes[1]['value']
        account_id = request_data['account_id']
        submit_threshold = request_data['submit_threshold']
        max_duration = request_data['max_duration']
        request_keys = request_data['request_keys']
        price_request: PriceRequest = PriceRequest.query(db_session).filter_by(order_id=purchase_id).first()
        if price_request:
            price_request.created_at = self.block.id
            price_request.created_by = account_id.replace('0x', '')
            price_request.symbols = request_keys
            price_request.prepayment = fee
        else:
            price_request: PriceRequest = PriceRequest(
                order_id=purchase_id,
                created_by=account_id.replace('0x', ''),
                symbols=request_keys,
                status=0,  # 0: pending,  1: successful, 2: failed
                prepayment=fee,
                payment=0,
                created_at=self.block.id,
                # auth=,
                # ended_at=
            )
        price_request.save(db_session)
