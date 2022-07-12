from app.models.data import SessionValidator
from app.processors.base import BlockProcessor
import dateutil


class BlockTotalProcessor(BlockProcessor):

    def sequencing_hook(self, db_session, parent_block_data, parent_sequenced_block_data):
        print('RUN 1 sequencing_hook Of BlockTotalProcessor start')
        if not parent_sequenced_block_data:
            parent_sequenced_block_data = {}

        if parent_block_data and parent_block_data['datetime']:
            self.sequenced_block.parent_datetime = parent_block_data['datetime']

            if type(parent_block_data['datetime']) is str:
                self.sequenced_block.blocktime = (
                            self.block.datetime - dateutil.parser.parse(parent_block_data['datetime'])).total_seconds()
            else:
                self.sequenced_block.blocktime = (self.block.datetime - parent_block_data['datetime']).total_seconds()
        else:
            self.sequenced_block.blocktime = 0
            self.sequenced_block.parent_datetime = self.block.datetime

        self.sequenced_block.total_extrinsics = int(
            parent_sequenced_block_data.get('total_extrinsics', 0)) + self.block.count_extrinsics
        self.sequenced_block.total_extrinsics_success = int(
            parent_sequenced_block_data.get('total_extrinsics_success', 0)) + self.block.count_extrinsics_success
        self.sequenced_block.total_extrinsics_error = int(
            parent_sequenced_block_data.get('total_extrinsics_error', 0)) + self.block.count_extrinsics_error
        self.sequenced_block.total_extrinsics_signed = int(
            parent_sequenced_block_data.get('total_extrinsics_signed', 0)) + self.block.count_extrinsics_signed
        self.sequenced_block.total_extrinsics_unsigned = int(
            parent_sequenced_block_data.get('total_extrinsics_unsigned', 0)) + self.block.count_extrinsics_unsigned
        self.sequenced_block.total_extrinsics_signedby_address = int(
            parent_sequenced_block_data.get('total_extrinsics_signedby_address',
                                            0)) + self.block.count_extrinsics_signedby_address
        self.sequenced_block.total_extrinsics_signedby_index = int(
            parent_sequenced_block_data.get('total_extrinsics_signedby_index',
                                            0)) + self.block.count_extrinsics_signedby_index
        self.sequenced_block.total_events = int(
            parent_sequenced_block_data.get('total_events', 0)) + self.block.count_events
        self.sequenced_block.total_events_system = int(
            parent_sequenced_block_data.get('total_events_system', 0)) + self.block.count_events_system
        self.sequenced_block.total_events_module = int(
            parent_sequenced_block_data.get('total_events_module', 0)) + self.block.count_events_module
        self.sequenced_block.total_events_extrinsic = int(
            parent_sequenced_block_data.get('total_events_extrinsic', 0)) + self.block.count_events_extrinsic
        self.sequenced_block.total_events_finalization = int(
            parent_sequenced_block_data.get('total_events_finalization', 0)) + self.block.count_events_finalization
        self.sequenced_block.total_events_transfer = int(
            parent_sequenced_block_data.get('total_events_transfer', 0)) + self.block.count_events_transfer
        self.sequenced_block.total_blocktime = int(
            parent_sequenced_block_data.get('total_blocktime', 0)) + self.sequenced_block.blocktime
        self.sequenced_block.total_accounts_new = int(
            parent_sequenced_block_data.get('total_accounts_new', 0)) + self.block.count_accounts_new

        self.sequenced_block.total_logs = int(parent_sequenced_block_data.get('total_logs', 0)) + self.block.count_log
        self.sequenced_block.total_accounts = int(
            parent_sequenced_block_data.get('total_accounts', 0)) + self.block.count_accounts
        self.sequenced_block.total_accounts_reaped = int(
            parent_sequenced_block_data.get('total_accounts_reaped', 0)) + self.block.count_accounts_reaped
        self.sequenced_block.total_sessions_new = int(
            parent_sequenced_block_data.get('total_sessions_new', 0)) + self.block.count_sessions_new
        self.sequenced_block.total_contracts_new = int(
            parent_sequenced_block_data.get('total_contracts_new', 0)) + self.block.count_contracts_new

        self.sequenced_block.session_id = int(parent_sequenced_block_data.get('session_id', 0))

        if parent_block_data and parent_block_data['count_sessions_new'] > 0:
            self.sequenced_block.session_id += 1

        if self.block.slot_number is not None:

            rank_validator = None

            if self.block.authority_index is not None:
                rank_validator = self.block.authority_index
            else:
                # In case of AURA, validator slot is determined by unique slot number
                validator_count = SessionValidator.query(db_session).filter_by(
                    session_id=self.sequenced_block.session_id
                ).count()

                if validator_count > 0:
                    rank_validator = int(self.block.slot_number) % validator_count

            # Retrieve block producer from session validator set
            validator = SessionValidator.query(db_session).filter_by(
                session_id=self.sequenced_block.session_id,
                rank_validator=rank_validator).first()

            if validator:
                self.sequenced_block.author = validator.validator_stash
