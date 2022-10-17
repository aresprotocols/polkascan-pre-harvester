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

        # print('attribute_data', attribute_value)

        # estimate_id = attribute_value['id']
        # estimate_symbol = attribute_value['symbol']
        # estimates_type = attribute_value['estimates_type']
        # estimates_ticket_price = attribute_value['ticket_price']
        # estimates_symbol_completed_price = attribute_value['symbol_completed_price']
        # estimates_symbol_fraction = attribute_value['symbol_fraction']
        # estimates_start = attribute_value['start']
        # estimates_end = attribute_value['end']
        # estimates_distribute = attribute_value['distribute']
        # estimates_multiplier = attribute_value['multiplier']
        # estimates_deviation = attribute_value['deviation']
        # estimates_range = attribute_value['range']
        # estimates_total_reward = attribute_value['total_reward']
        # estimates_state = attribute_value['state']
        # estimates_created_at = self.block.datetime
        #
        # print(estimate_id,'-#-', estimate_symbol,'-#-', estimates_type,'-#-', estimates_ticket_price,'-#-',
        #       estimates_symbol_completed_price,'-#-', estimates_symbol_fraction,'-#-', estimates_start,'-#-',
        #       estimates_end,'-#-', estimates_distribute,'-#-', estimates_multiplier,'-#-', estimates_deviation,'-#-',
        #       estimates_range,'-#-', estimates_total_reward,'-#-', estimates_state )
        #
        # data_item = EstimatesDataList(
        #     estimate_id=estimate_id,
        #     symbol=estimate_symbol,
        #     symbol_fraction=estimates_symbol_fraction,
        #     state=estimates_state,
        #     start=estimates_start,
        #     end=estimates_end,
        #     distribute=estimates_distribute,
        #     range_data=estimates_range,
        #     deviation=estimates_deviation,
        #     multiplier=str(estimates_multiplier),
        #     ticket_price=estimates_ticket_price,
        #     estimates_type=estimates_type,
        #     created_at=estimates_created_at,
        #     block_id=self.event.block_id,
        # )
        data_item = EstimatesDataList().fill_data(attributes=attribute_value, block=self.block, event=self.event)
        data_item.save(db_session)

    def accumulation_revert(self, db_session):
        print("Estimates.NewEstimates - accumulation_revert ", self.block.id)
        for item in EstimatesDataList.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)
