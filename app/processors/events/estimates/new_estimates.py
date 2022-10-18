# CompletedEstimates

from app.models.data import EstimatesParticipants, EstimatesWinner, EstimatesDataList
from app.processors.base import EventProcessor
from scalecodec.types import ss58_encode
from app.settings import SUBSTRATE_ADDRESS_TYPE


class EstimatesNewEstimates(EventProcessor):
    module_id = 'Estimates'
    event_id = 'NewEstimates'

    def accumulation_hook(self, db_session):
        print("Estimates.NewEstimates - accumulation_hook")
        attribute_data = self.event.attributes
        print('attribute_data', attribute_data)
        attribute_value = attribute_data[0]['value']

        data_item = EstimatesDataList().fill_data(attributes=attribute_value, block=self.block, event=self.event)
        data_item.save(db_session)

    def accumulation_revert(self, db_session):
        print("Estimates.NewEstimates - accumulation_revert ", self.block.id)
        for item in EstimatesDataList.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)
