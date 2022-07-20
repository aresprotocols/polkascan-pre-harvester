from app.models.data import EstimatesParticipants
from app.processors.base import EventProcessor


class ParticipateEstimates(EventProcessor):
    module_id = 'Estimates'
    event_id = 'ParticipateEstimates'

    def accumulation_hook(self, db_session):
        print("participate")
        print(self.event.attributes)
        # Check event requirements
        if len(self.event.attributes) == 4:
            symbol = self.event.attributes[0]['value']
            estimate_id = self.event.attributes[1]['value']
            participant = self.event.attributes[3]['value'].replace('0x', '')
            price = self.event.attributes[2]['value']['estimates']
            option_index = self.event.attributes[2]['value']['range_index']
            estimate_type = 'option' if option_index else 'price'
        else:
            raise ValueError('Event doensn\'t meet requirements')

        participant = EstimatesParticipants(
            symbol=symbol,
            estimate_id=estimate_id,
            estimate_type=estimate_type,
            participant=participant,
            price=price,
            option_index=option_index,
            created_at=self.event.block_id
        )

        participant.save(db_session)
