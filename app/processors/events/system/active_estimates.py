# CompletedEstimates

from app.models.data import EstimatesParticipants, EstimatesWinner, EstimatesDataList
from app.processors.base import EventProcessor
from scalecodec.types import ss58_encode
from app.settings import SUBSTRATE_ADDRESS_TYPE


class EstimatesActiveEstimates(EventProcessor):
    module_id = 'Estimates'
    event_id = 'ActiveEstimates'

    def accumulation_hook(self, db_session):
        print("Estimates.ActiveEstimates - accumulation_hook")
        attribute_data = self.event.attributes
        print('attribute_data', attribute_data)
        attribute_value = attribute_data[0]['value']

        estimate_id = attribute_value['id']
        symbol = attribute_value['symbol']
        symbol_completed_price = str(attribute_value['symbol_completed_price'])
        total_reward = str(attribute_value['total_reward'])
        estimate_state = attribute_value['state']

        estimate_data: EstimatesDataList = EstimatesDataList.query(db_session).filter_by(symbol=symbol,
                                                                                         estimate_id=estimate_id).first()
        if estimate_data:
            estimate_data.state = estimate_state
            estimate_data.symbol_completed_price = symbol_completed_price
            estimate_data.total_reward = total_reward
            estimate_data.save(db_session)
        else:
            estimate_data = EstimatesDataList().fill_data(attributes=attribute_value, block=self.block, event=self.event)
            estimate_data.save(db_session)

    def accumulation_revert(self, db_session):
        print("Estimates.ActiveEstimates - accumulation_revert ", self.block.id)
        for item in EstimatesDataList.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)
