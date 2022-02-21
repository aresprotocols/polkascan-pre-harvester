from app.models.data import EraPriceRequest
from app.processors import EventProcessor


class NewPurchaseRequestEventProcessor(EventProcessor):
    module_id = 'AresOracle'
    event_id = 'NewPurchasedRequest'

    def accumulation_hook(self, db_session):
        attributes = self.event.attributes
        purchase_id = attributes[0]['value']
        fee = attributes[2]['value']
        era = attributes[3]['value']
        price_request: EraPriceRequest = EraPriceRequest.query(db_session).filter_by(era=era).first()

        # exist
        if price_request:
            price_request.era_total_requests += 1
            price_request.save(db_session)
        else:
            previous: EraPriceRequest = EraPriceRequest.query(db_session).filter_by(era=era - 1).first()
            price_request = EraPriceRequest(
                era=era,
                total_eras=previous.total_eras + 1 if previous else 0,
                era_total_requests=1,
                era_total_points=0,
                era_total_fee=0
            )
            price_request.save(db_session)

        # request_data = attributes[1]['value']
        # account_id = request_data['account_id']
        # submit_threshold = request_data['submit_threshold']
        # max_duration = request_data['max_duration']
        # request_keys = request_data['request_keys']
        # price_request: EraPriceRequest = EraPriceRequest(
        #     purchase_id=purchase_id,
        #     block_id=self.block.id,
        #     account_id=account_id.replace('0x', ''),
        #     fee=fee,
        #     submit_threshold=submit_threshold,
        #     max_duration=max_duration,
        #     request_keys=request_keys,
        # )
        # price_request.save(db_session)
