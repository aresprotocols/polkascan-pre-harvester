from app.models.data import EstimatesParticipants
from app.processors.base import EventProcessor


class ParticipateEstimates(EventProcessor):
    module_id = 'Estimates'
    event_id = 'ParticipateEstimates'

    def accumulation_hook(self, db_session):
        print("participate")
        print(self.event.attributes, len(self.event.attributes))
        # Check event requirements
        if len(self.event.attributes) == 4:
            symbol = self.event.attributes[0]['value']
            estimate_id = self.event.attributes[1]['value']
            participant = self.event.attributes[3]['value'].replace('0x', '')
            price = self.event.attributes[2]['value']['estimates']
            option_index = self.event.attributes[2]['value']['range_index']
            estimate_type = 'price'
            if price is None:
                estimate_type = 'range'
        else:
            raise ValueError('Event doensn\'t meet requirements')

        participant = EstimatesParticipants(
            symbol=symbol,
            estimate_id=estimate_id,
            estimate_type=estimate_type,
            option_index=option_index,
            participant=participant,
            price=price,
            block_id=self.event.block_id
        )

        participant.save(db_session)

    def accumulation_revert(self, db_session):
        print("estimates.participate - accumulation_revert ", self.block.id)
        for item in EstimatesParticipants.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)
