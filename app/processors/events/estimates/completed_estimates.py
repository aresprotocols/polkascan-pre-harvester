# CompletedEstimates

from app.models.data import EstimatesParticipants, EstimatesWinner
from app.processors.base import EventProcessor
from scalecodec.types import ss58_encode
from app.settings import SUBSTRATE_ADDRESS_TYPE


# Data case:
# [{
# 	'type': 'SymbolEstimatesConfig<T::BlockNumber, BalanceOf<T>>',
# 	'value': {
# 		'symbol': 'btc-usdt',
# 		'estimates_type': 'DEVIATION',
# 		'id': 1,
# 		'ticket_price': 10000000000000,
# 		'symbol_completed_price': 187706153,
# 		'symbol_fraction': 4,
# 		'start': 769038,
# 		'end': 769058,
# 		'distribute': 769078,
# 		'multiplier': [{
# 			'Base': 1
# 		}, {
# 			'Base': 3
# 		}, {
# 			'Base': 5
# 		}],
# 		'deviation': 100000,
# 		'range': None,
# 		'total_reward': 120000000000000,
# 		'state': 'Completed'
# 	}
# }, {
# 	'type': 'Vec<(T::AccountId, BalanceOf<T>)>',
# 	'value': [('0x5cd05488afc2dd05334eec23bf6e5b9ef31d38d5a3d42202ffeca6aa44ff5820', 60000000000000), ('0x6239c2f6b6f921d070a9f8cb1eab7d2783d0e71cc436736a19e83871dcd59816', 60000000000000)]
# }]
class EstimatesCompletedEstimates(EventProcessor):
    module_id = 'Estimates'
    event_id = 'CompletedEstimates'

    def accumulation_hook(self, db_session):
        print("Estimates.CompletedEstimates Run In")
        # print(self.event.attributes, len(self.event.attributes))

        attribute_data = self.event.attributes
        if len(attribute_data) >= 2:
            estimates_config_data = attribute_data[0]['value']
            winner_list = attribute_data[1]['value']

            symbol = estimates_config_data['symbol']
            estimate_id = estimates_config_data['id']
            estimate_type = estimates_config_data['estimates_type']
            created_at = self.block.datetime

            for winner_item in winner_list:
                winner_acc = winner_item[0].replace('0x', '')
                reward = winner_item[1]

                db_data = EstimatesWinner(
                    symbol=symbol,
                    estimate_id=estimate_id,
                    estimate_type=estimate_type,
                    created_at=created_at,
                    ss58_address=ss58_encode(winner_acc, SUBSTRATE_ADDRESS_TYPE),
                    public_key=winner_acc,
                    reward=reward,
                    block_id=self.event.block_id,
                )

                db_data.save(db_session)

        else:
            print("Current runtime events can not supported winner record.")

        # db_data = EstimatesWinner (
        #     symbol = sa.Column('symbol', sa.String(length=30), nullable=False)
        #     estimate_id = sa.Column('estimate_id', sa.Integer(), nullable=False)
        #     estimate_type = sa.Column('estimate_type', sa.String(length=30), nullable=False)
        #     ss58_address = sa.Column('ss58_address', sa.String(length=48), nullable=False)
        #     public_key = sa.Column('public_key', sa.String(length=64), nullable=False)
        #     reward = sa.Column('reward', sa.Numeric(precision=65, scale=0), nullable=False)
        #     created_at = sa.Column('created_at', sa.DateTime(timezone=True), nullable=True)
        # )
        # Check event requirements
        # if len(self.event.attributes) >= 4:
        #     symbol = self.event.attributes[0]['value']
        #     estimate_id = self.event.attributes[1]['value']
        #     participant = self.event.attributes[3]['value'].replace('0x', '')
        #     ss58_address = ss58_encode(participant, SUBSTRATE_ADDRESS_TYPE)
        #     price = self.event.attributes[2]['value']['estimates']
        #     option_index = self.event.attributes[2]['value']['range_index']
        #
        # if len(self.event.attributes) == 4:
        #     estimate_type = 'price'
        #     if price is None:
        #         estimate_type = 'range'
        # elif len(self.event.attributes) == 5:
        #     # symbol = self.event.attributes[0]['value']
        #     # estimate_id = self.event.attributes[1]['value']
        #     # participant = self.event.attributes[3]['value'].replace('0x', '')
        #     # price = self.event.attributes[2]['value']['estimates']
        #     # option_index = self.event.attributes[2]['value']['range_index']
        #     estimate_type = 'price'
        #     # print('estimate_type', self.event.attributes[4]['value'])
        #     if self.event.attributes[4]['value'] == 'RANGE':
        #         estimate_type = 'range'
        # else:
        #     raise ValueError('Event doensn\'t meet requirements')

        # participant = EstimatesParticipants(
        #     symbol=symbol,
        #     estimate_id=estimate_id,
        #     estimate_type=estimate_type,
        #     option_index=option_index,
        #     participant=participant,
        #     ss58_address=ss58_address,
        #     created_at=self.block.datetime,
        #     price=price,
        #     block_id=self.event.block_id
        # )
        #
        # participant.save(db_session)

    def accumulation_revert(self, db_session):
        print("Estimates.CompletedEstimates - accumulation_revert ", self.block.id)
        # for item in EstimatesParticipants.query(db_session).filter_by(block_id=self.block.id):
        #     db_session.delete(item)
