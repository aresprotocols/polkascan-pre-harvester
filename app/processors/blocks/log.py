from app.models.data import Log
from app.processors.base import BlockProcessor
from scalecodec.base import ScaleBytes


class LogBlockProcessor(BlockProcessor):

    def accumulation_hook(self, db_session):
        log_digest_cls = self.substrate.runtime_config.get_decoder_class('sp_runtime::generic::digest::DigestItem')

        if log_digest_cls is None:
            raise NotImplementedError("No decoding class found for 'DigestItem'")

        self.block.count_log = len(self.block.logs)
        for idx, log_data in enumerate(self.block.logs):
            log_digest = log_digest_cls(data=ScaleBytes(log_data))
            log_digest.decode()

            log_type = log_digest.value_object[0]  # ('PreRuntime', GenericPreRuntime)
            # print(log_digest.value[log_type])
            log_inner_data = {}
            if ('PreRuntime' == log_type or 'Seal' == log_type) and self.substrate.implements_scaleinfo():
                engine_id = bytes.fromhex(log_digest.value[log_type][0][2:]).decode('utf-8')
                if engine_id == 'aura' and 'PreRuntime' == log_type:
                    predigest_data = log_digest.value['PreRuntime'][1]
                    if predigest_data[:2] != '0x':
                        predigest_data = f"0x{predigest_data.encode().hex()}"
                    aura_predigest = self.substrate.runtime_config.create_scale_object(
                        type_string='RawAuraPreDigest',
                        # data=ScaleBytes(log_digest.value['PreRuntime'][1])
                        data=ScaleBytes(predigest_data)
                    )
                    aura_predigest.decode()
                    slot_number = aura_predigest.value['slot_number']
                    log_inner_data = {"data": {"slot_number": slot_number}, "engine": "aura"}
                elif engine_id == 'aura' and 'Seal' == log_type:
                    log_inner_data = {"data": log_digest.value['Seal'][1], "engine": "aura"}

                elif engine_id == 'BABE' and 'PreRuntime' == log_type:
                    babe_predigest = self.substrate.runtime_config.create_scale_object(
                        type_string='RawBabePreDigest',
                        data=ScaleBytes(log_digest.value['PreRuntime'][1])
                    )
                    babe_predigest.decode()
                    rank_validator = babe_predigest[1].value['authority_index']
                    slot_number = babe_predigest[1].value['slot_number']
                    log_inner_data = {"data": {"slot_number": slot_number, "authority_index": rank_validator},
                                      "engine": "BABE"}
                elif engine_id == 'BABE' and 'Seal' == log_type:
                    log_inner_data = {"data": log_digest.value['Seal'][1], "engine": "BABE"}
            else:
                if type(log_digest.value) == str:
                    log_inner_data = log_digest.value
                else:
                    log_inner_data = log_digest.value[log_type]

            log = Log(
                block_id=self.block.id,
                log_idx=idx,
                type_id=log_digest.index,
                type=log_type,
                data=log_inner_data,
            )

            if log_type == 'PreRuntime':
                if log.data['engine'] == 'BABE':
                    # Determine block producer
                    self.block.authority_index = log.data['data']['authority_index']
                    self.block.slot_number = log.data['data']['slot_number']

                if log.data['engine'] == 'aura':
                    self.block.slot_number = log.data['data']['slot_number']

            log.save(db_session)

    def accumulation_revert(self, db_session):
        for item in Log.query(db_session).filter_by(block_id=self.block.id):
            db_session.delete(item)

        self.block.authority_index = None
        self.block.slot_number = None
