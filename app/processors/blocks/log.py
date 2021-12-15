from app.models.data import Log
from app.processors.base import BlockProcessor
from scalecodec.base import ScaleBytes


class LogBlockProcessor(BlockProcessor):

    def accumulation_hook(self, db_session):

        self.block.count_log = len(self.block.logs)
        for idx, log_data in enumerate(self.block.logs):
            log_digest = self.substrate.runtime_config.create_scale_object(
                "DigestItem", data=ScaleBytes(log_data)
            )
            log_digest.decode()

            log_type = log_digest.value_object[0]  # ('PreRuntime', GenericPreRuntime)
            log = Log(
                block_id=self.block.id,
                log_idx=idx,
                type_id=log_digest.index,
                type=log_type,
                data=log_digest.value[log_type],
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
