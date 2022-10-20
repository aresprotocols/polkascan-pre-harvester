from app.models.data import EstimatesParticipants
from app.processors.base import EventProcessor
from scalecodec.types import ss58_encode
from app.settings import SUBSTRATE_ADDRESS_TYPE


class ParticipateEstimates(EventProcessor):
    module_id = 'Estimates'
    event_id = 'ParticipateEstimates'

    def accumulation_hook(self, db_session):
        print("#### = ParticipateEstimates")
        # print(self.event.attributes, len(self.event.attributes))
        # Check event requirements
        if len(self.event.attributes) >= 4:
            symbol = self.event.attributes[0]['value']
            estimate_id = self.event.attributes[1]['value']
            participant = self.event.attributes[3]['value'].replace('0x', '')
            ss58_address = ss58_encode(participant, SUBSTRATE_ADDRESS_TYPE)
            price = self.event.attributes[2]['value']['estimates']
            end = self.event.attributes[2]['value']['end']
            option_index = self.event.attributes[2]['value']['range_index']
            deposit = None

        if len(self.event.attributes) == 4:
            estimate_type = 'deviation'
            if price is None:
                estimate_type = 'range'
        elif len(self.event.attributes) == 5:
            estimate_type = 'deviation'
            if self.event.attributes[4]['value'] == 'RANGE':
                estimate_type = 'range'
        elif len(self.event.attributes) == 6:
            estimate_type = 'deviation'
            if self.event.attributes[4]['value'] == 'RANGE':
                estimate_type = 'range'
            deposit = self.event.attributes[5]['value']
        else:
            raise ValueError('Event doensn\'t meet requirements')


        # Will delete before insert first that is use to fix cannot be inserted repeatedly.
        # Symbol-ID-participant
        # doge-usdt-0-ac2287708630b1f0b7155e02bfde05e20f4de09271fcdd7dd864
        for item in EstimatesParticipants.query(db_session).filter_by(symbol=symbol,
                                                                      estimate_id=estimate_id,
                                                                      participant=participant,
                                                                      estimate_type=estimate_type):
            db_session.delete(item)
            db_session.flush()

        participant = EstimatesParticipants(
            symbol=symbol,
            estimate_id=estimate_id,
            estimate_type=estimate_type,
            option_index=option_index,
            participant=participant,
            ss58_address=ss58_address,
            created_at=self.block.datetime,
            price=price,
            end=end,
            block_id=self.event.block_id,
            deposit=deposit,
        )
        participant.save(db_session)

    def accumulation_revert(self, db_session):
        print("estimates.participate - accumulation_revert ", self.block.id)
        for item in EstimatesParticipants.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)
