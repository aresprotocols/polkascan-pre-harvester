from app.models.data import EraPriceRequest
from app.processors import EventProcessor


class EndOfAskEraEventProcessor(EventProcessor):
    module_id = 'OracleFinance'
    event_id = 'EndOfAskEra'

    def accumulation_hook(self, db_session):
        attributes = self.event.attributes
        era = attributes[0]['value']
        era_price_request: EraPriceRequest = EraPriceRequest.query(db_session).filter_by(era=era).first()
        if era_price_request:
            era_price_request.era_total_fee = attributes[1]['value']
            era_price_request.era_total_points = attributes[2]['value']
            era_price_request.ended_at = self.block.id
            era_price_request.save(db_session)
        else:
            # TODO fix
            print("price_request not exist skip this event")

