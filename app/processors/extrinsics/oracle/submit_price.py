from app.models.data import SymbolSnapshot
from app.processors import ExtrinsicProcessor


class AresOracleSubmitPrice(ExtrinsicProcessor):
    module_id = 'AresOracle'
    call_id = 'submit_price_unsigned_with_signed_payload'

    def accumulation_hook(self, db_session):
        # print(self.extrinsic.params)
        extrinsic = self.extrinsic.params[0]['value']
        account_id = extrinsic['auth']
        block_number = self.block.id
        # print("block_number:{},account_id:{}".format(block_number, account_id))
        # for price in extrinsic['price']:
        #     symbol = price[0]
        #     timestamp = price[4]
        #     exponent = price[3]['exponent']
        #     integer_part = price[3]['integer']
        #     fraction_part = price[3]['fraction']
        #     fraction_length = price[3]['fraction_length']
        #     snapshot = SymbolPriceSnapshot(
        #         block_id=block_number,
        #         account_id=account_id.replace('0x', ''),
        #         symbol=symbol,
        #         exponent=exponent,
        #         fraction_part=fraction_part,
        #         fraction_length=fraction_length,
        #         integer_part=integer_part,
        #         created_at=timestamp
        #     )
        #     snapshot.save(db_session)
