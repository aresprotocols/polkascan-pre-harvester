from app.models.data import EraPriceRequest
from app.processors import EventProcessor


class EndOfAskEraEventProcessor(EventProcessor):
    module_id = 'OracleFinance'
    event_id = 'EndOfAskEra'

    def accumulation_hook(self, db_session):
        attributes = self.event.attributes
        era = attributes[0]['value']
        price_request: EraPriceRequest = EraPriceRequest.query(db_session).filter_by(era=era).first()
        if price_request:
            price_request.era_total_fee = attributes[1]['value']
            price_request.era_total_points = attributes[2]['value']
            price_request.ended_at = self.block.id
        else:
            print("price_request not exist skip this event")

