#  Polkascan PRE Harvester
#
#  Copyright 2018-2020 openAware BV (NL).
#  This file is part of Polkascan.
#
#  Polkascan is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Polkascan is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Polkascan. If not, see <http://www.gnu.org/licenses/>.
#
#  data.py

import sqlalchemy as sa
from sqlalchemy import text, UniqueConstraint
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Block(BaseModel):
    __tablename__ = 'data_block'

    serialize_exclude = ['debug_info']

    serialize_type = 'block'

    id = sa.Column(sa.Integer(), primary_key=True, autoincrement=False)
    parent_id = sa.Column(sa.Integer(), nullable=False)
    hash = sa.Column(sa.String(66), unique=True, index=True, nullable=False)
    parent_hash = sa.Column(sa.String(66), index=True, nullable=False)
    state_root = sa.Column(sa.String(66), nullable=False)
    extrinsics_root = sa.Column(sa.String(66), nullable=False)
    count_extrinsics = sa.Column(sa.Integer(), nullable=False)
    count_extrinsics_unsigned = sa.Column(sa.Integer(), nullable=False)
    count_extrinsics_signed = sa.Column(sa.Integer(), nullable=False)
    count_extrinsics_error = sa.Column(sa.Integer(), nullable=False)
    count_extrinsics_success = sa.Column(sa.Integer(), nullable=False)
    count_extrinsics_signedby_address = sa.Column(sa.Integer(), nullable=False)
    count_extrinsics_signedby_index = sa.Column(sa.Integer(), nullable=False)
    count_events = sa.Column(sa.Integer(), nullable=False)
    count_events_system = sa.Column(sa.Integer(), nullable=False)
    count_events_module = sa.Column(sa.Integer(), nullable=False)
    count_events_extrinsic = sa.Column(sa.Integer(), nullable=False)
    count_events_finalization = sa.Column(sa.Integer(), nullable=False)
    count_events_transfer = sa.Column(sa.Integer(), nullable=False)
    count_accounts = sa.Column(sa.Integer(), nullable=False)
    count_accounts_new = sa.Column(sa.Integer(), nullable=False)
    count_accounts_reaped = sa.Column(sa.Integer(), nullable=False)
    count_sessions_new = sa.Column(sa.Integer(), nullable=False)
    count_contracts_new = sa.Column(sa.Integer(), nullable=False)
    count_log = sa.Column(sa.Integer(), nullable=False)
    range10000 = sa.Column(sa.Integer(), nullable=False)
    range100000 = sa.Column(sa.Integer(), nullable=False)
    range1000000 = sa.Column(sa.Integer(), nullable=False)
    datetime = sa.Column(sa.DateTime(timezone=True))
    year = sa.Column(sa.Integer(), nullable=True)
    month = sa.Column(sa.Integer(), nullable=True)
    week = sa.Column(sa.Integer(), nullable=True)
    day = sa.Column(sa.Integer(), nullable=True)
    hour = sa.Column(sa.Integer(), nullable=True)
    full_month = sa.Column(sa.Integer(), nullable=True)
    full_week = sa.Column(sa.Integer(), nullable=True)
    full_day = sa.Column(sa.Integer(), nullable=True)
    full_hour = sa.Column(sa.Integer(), nullable=True)
    logs = sa.Column(sa.JSON(), default=None, server_default=None)
    authority_index = sa.Column(sa.Integer(), nullable=True)
    slot_number = sa.Column(sa.Numeric(precision=65, scale=0), nullable=True)
    spec_version_id = sa.Column(sa.String(64), nullable=False)
    debug_info = sa.Column(sa.JSON(), default=None, server_default=None)

    def set_datetime(self, datetime):
        self.datetime = datetime
        self.year = self.datetime.year
        self.month = self.datetime.month
        self.week = self.datetime.strftime("%W")
        self.day = self.datetime.day
        self.hour = self.datetime.hour
        self.full_month = self.datetime.strftime("%Y%m")
        self.full_week = self.datetime.strftime("%Y%W")
        self.full_day = self.datetime.strftime("%Y%m%d")
        self.full_hour = self.datetime.strftime("%Y%m%d%H")

    @classmethod
    def get_head(cls, session):
        with session.begin():
            query = session.query(cls)
            model = query.order_by(cls.id.desc()).first()

        return model

    @classmethod
    def get_missing_block_ids(cls, session):
        # return session.execute(text("""
        #                                     SELECT
        #                                       z.expected as block_from, z.got-1 as block_to
        #                                     FROM (
        #                                      SELECT
        #                                       @rownum:=@rownum+1 AS expected,
        #                                       IF(@rownum=id, 0, @rownum:=id) AS got
        #                                      FROM
        #                                       (SELECT @rownum:=0) AS a
        #                                       JOIN data_block
        #                                       ORDER BY id
        #                                      ) AS z
        #                                     WHERE z.got!=0
        #                                     ORDER BY block_from DESC
        #                                     """)
        #                        )
        return session.execute(text("""
                                                    SELECT
                                                      z.expected as block_from, z.got-1 as block_to
                                                    FROM (
                                                     SELECT
                                                      @rownum:=@rownum+1 AS expected,
                                                      IF(@rownum=id, 0, @rownum:=id) AS got
                                                     FROM
                                                      (SELECT @rownum:=6289000) AS a
                                                      JOIN data_block
                                                      WHERE data_block.id > 6289000
                                                      ORDER BY id
                                                     ) AS z
                                                    WHERE z.got!=0
                                                    ORDER BY block_from DESC
                                                    """)
                               )


class BlockTotal(BaseModel):
    __tablename__ = 'data_block_total'

    id = sa.Column(sa.Integer(), primary_key=True, autoincrement=False)
    session_id = sa.Column(sa.Integer())
    parent_datetime = sa.Column(sa.DateTime())
    blocktime = sa.Column(sa.Integer(), nullable=False)
    author = sa.Column(sa.String(64), nullable=True, index=True)
    total_extrinsics = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_extrinsics_success = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_extrinsics_error = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_extrinsics_signed = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_extrinsics_unsigned = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_extrinsics_signedby_address = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_extrinsics_signedby_index = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_events = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_events_system = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_events_module = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_events_extrinsic = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_events_finalization = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_events_transfer = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_logs = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_blocktime = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_accounts = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_accounts_new = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_accounts_reaped = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_sessions_new = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_contracts_new = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    total_treasury_burn = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)


class Event(BaseModel):
    __tablename__ = 'data_event'

    block_id = sa.Column(sa.Integer(), primary_key=True, index=True)
    block = relationship(Block, foreign_keys=[block_id], primaryjoin=block_id == Block.id)

    event_idx = sa.Column(sa.Integer(), primary_key=True, index=True)

    extrinsic_idx = sa.Column(sa.Integer(), index=True)

    type = sa.Column(sa.String(4), index=True)

    spec_version_id = sa.Column(sa.Integer())

    module_id = sa.Column(sa.String(64), index=True)
    event_id = sa.Column(sa.String(64), index=True)

    system = sa.Column(sa.SmallInteger(), index=True, nullable=False)
    module = sa.Column(sa.SmallInteger(), index=True, nullable=False)
    phase = sa.Column(sa.SmallInteger())

    attributes = sa.Column(sa.JSON())

    codec_error = sa.Column(sa.Boolean())

    def serialize_id(self):
        return '{}-{}'.format(self.block_id, self.event_idx)


class Extrinsic(BaseModel):
    __tablename__ = 'data_extrinsic'

    block_id = sa.Column(sa.Integer(), primary_key=True, index=True)
    block = relationship(Block, foreign_keys=[block_id], primaryjoin=block_id == Block.id)

    extrinsic_idx = sa.Column(sa.Integer(), primary_key=True, index=True)
    extrinsic_hash = sa.Column(sa.String(64), index=True, nullable=True)

    extrinsic_length = sa.Column(sa.String(10))
    extrinsic_version = sa.Column(sa.String(2))

    signed = sa.Column(sa.SmallInteger(), index=True, nullable=False)
    unsigned = sa.Column(sa.SmallInteger(), index=True, nullable=False)
    signedby_address = sa.Column(sa.SmallInteger(), nullable=False)
    signedby_index = sa.Column(sa.SmallInteger(), nullable=False)

    address_length = sa.Column(sa.String(2))
    address = sa.Column(sa.String(64), index=True)
    account_index = sa.Column(sa.String(16), index=True)
    account_idx = sa.Column(sa.Integer(), index=True)
    signature = sa.Column(sa.String(130))
    nonce = sa.Column(sa.Integer())

    era = sa.Column(sa.String(20))

    call = sa.Column(sa.String(4))
    module_id = sa.Column(sa.String(64), index=True)
    call_id = sa.Column(sa.String(64), index=True)
    params = sa.Column(sa.JSON())

    success = sa.Column(sa.SmallInteger(), default=0, nullable=False)
    error = sa.Column(sa.SmallInteger(), default=0, nullable=False)

    spec_version_id = sa.Column(sa.Integer())

    codec_error = sa.Column(sa.Boolean(), default=False)

    def serialize_id(self):
        return '{}-{}'.format(self.block_id, self.extrinsic_idx)


class Log(BaseModel):
    __tablename__ = 'data_log'

    block_id = sa.Column(sa.Integer(), primary_key=True, autoincrement=False)
    log_idx = sa.Column(sa.Integer(), primary_key=True, autoincrement=False)
    type_id = sa.Column(sa.Integer(), index=True)
    type = sa.Column(sa.String(64))
    data = sa.Column(sa.JSON())


class Account(BaseModel):
    __tablename__ = 'data_account'

    id = sa.Column(sa.String(64), primary_key=True)
    address = sa.Column(sa.String(48), index=True)
    index_address = sa.Column(sa.String(24), index=True)
    is_reaped = sa.Column(sa.Boolean, default=False)

    is_validator = sa.Column(sa.Boolean, default=False, index=True)
    was_validator = sa.Column(sa.Boolean, default=False, index=True)
    is_nominator = sa.Column(sa.Boolean, default=False, index=True)
    was_nominator = sa.Column(sa.Boolean, default=False, index=True)
    is_council_member = sa.Column(sa.Boolean, default=False, index=True)
    was_council_member = sa.Column(sa.Boolean, default=False, index=True)
    is_tech_comm_member = sa.Column(sa.Boolean, default=False, index=True)
    was_tech_comm_member = sa.Column(sa.Boolean, default=False, index=True)
    is_registrar = sa.Column(sa.Boolean, default=False, index=True)
    was_registrar = sa.Column(sa.Boolean, default=False, index=True)
    is_sudo = sa.Column(sa.Boolean, default=False, index=True)
    was_sudo = sa.Column(sa.Boolean, default=False, index=True)

    is_treasury = sa.Column(sa.Boolean, default=False, index=True)
    is_contract = sa.Column(sa.Boolean, default=False, index=True)

    count_reaped = sa.Column(sa.Integer(), default=0)
    hash_blake2b = sa.Column(sa.String(64), index=True, nullable=True)

    balance_total = sa.Column(sa.Numeric(precision=65, scale=0), nullable=True, index=True)
    balance_free = sa.Column(sa.Numeric(precision=65, scale=0), nullable=True, index=True)
    balance_reserved = sa.Column(sa.Numeric(precision=65, scale=0), nullable=True, index=True)
    nonce = sa.Column(sa.Integer(), nullable=True)
    account_info = sa.Column(sa.JSON(), default=None, server_default=None, nullable=True)

    has_identity = sa.Column(sa.Boolean, default=False, index=True)
    has_subidentity = sa.Column(sa.Boolean, default=False, index=True)
    identity_display = sa.Column(sa.String(32), index=True, nullable=True)
    identity_legal = sa.Column(sa.String(32), nullable=True)
    identity_web = sa.Column(sa.String(32), nullable=True)
    identity_riot = sa.Column(sa.String(32), nullable=True)
    identity_email = sa.Column(sa.String(32), nullable=True)
    identity_twitter = sa.Column(sa.String(32), nullable=True)
    identity_judgement_good = sa.Column(sa.Integer(), default=0)
    identity_judgement_bad = sa.Column(sa.Integer(), default=0)
    parent_identity = sa.Column(sa.String(64), index=True, nullable=True)
    subidentity_display = sa.Column(sa.String(32), nullable=True)

    created_at_block = sa.Column(sa.Integer(), nullable=False)
    updated_at_block = sa.Column(sa.Integer(), nullable=False)


class AccountAudit(BaseModel):
    __tablename__ = 'data_account_audit'

    id = sa.Column(sa.Integer(), primary_key=True, autoincrement=True)
    account_id = sa.Column(sa.String(64))
    block_id = sa.Column(sa.Integer(), index=True, nullable=False)
    extrinsic_idx = sa.Column(sa.Integer())
    event_idx = sa.Column(sa.Integer())
    type_id = sa.Column(sa.Integer(), nullable=False)
    data = sa.Column(sa.JSON(), default=None, server_default=None, nullable=True)


class AccountInfoSnapshot(BaseModel):
    __tablename__ = 'data_account_info_snapshot'

    block_id = sa.Column(sa.Integer(), primary_key=True, index=True)
    account_id = sa.Column(sa.String(64), primary_key=True, index=True)

    balance_total = sa.Column(sa.Numeric(precision=65, scale=0), nullable=True, index=True)
    balance_free = sa.Column(sa.Numeric(precision=65, scale=0), nullable=True, index=True)
    balance_reserved = sa.Column(sa.Numeric(precision=65, scale=0), nullable=True, index=True)
    nonce = sa.Column(sa.Integer(), nullable=True)
    account_info = sa.Column(sa.JSON(), default=None, server_default=None, nullable=True)


class Session(BaseModel):
    __tablename__ = 'data_session'

    id = sa.Column(sa.Integer(), primary_key=True, autoincrement=False)
    start_at_block = sa.Column(sa.Integer())
    era = sa.Column(sa.Integer())
    era_idx = sa.Column(sa.Integer())
    created_at_block = sa.Column(sa.Integer(), nullable=False)
    created_at_extrinsic = sa.Column(sa.Integer())
    created_at_event = sa.Column(sa.Integer())
    count_validators = sa.Column(sa.Integer())
    count_nominators = sa.Column(sa.Integer())


class SessionTotal(BaseModel):
    __tablename__ = 'data_session_total'

    id = sa.Column(sa.Integer(), primary_key=True, autoincrement=False)
    end_at_block = sa.Column(sa.Integer())
    count_blocks = sa.Column(sa.Integer())


class SessionValidator(BaseModel):
    __tablename__ = 'data_session_validator'

    session_id = sa.Column(sa.Integer(), primary_key=True, autoincrement=False)
    rank_validator = sa.Column(sa.Integer(), primary_key=True, autoincrement=False, index=True)
    validator_stash = sa.Column(sa.String(64), index=True)
    validator_controller = sa.Column(sa.String(64), index=True)
    validator_session = sa.Column(sa.JSON(), default=None, server_default=None, nullable=True)
    bonded_total = sa.Column(sa.Numeric(precision=65, scale=0))
    bonded_active = sa.Column(sa.Numeric(precision=65, scale=0))
    bonded_nominators = sa.Column(sa.Numeric(precision=65, scale=0))
    bonded_own = sa.Column(sa.Numeric(precision=65, scale=0))
    unlocking = sa.Column(sa.JSON(), default=None, server_default=None, nullable=True)
    count_nominators = sa.Column(sa.Integer(), nullable=True)
    unstake_threshold = sa.Column(sa.Integer(), nullable=True)
    commission = sa.Column(sa.Numeric(precision=65, scale=0), nullable=True)


class SessionNominator(BaseModel):
    __tablename__ = 'data_session_nominator'

    session_id = sa.Column(sa.Integer(), primary_key=True, autoincrement=False)
    rank_validator = sa.Column(sa.Integer(), primary_key=True, autoincrement=False, index=True)
    rank_nominator = sa.Column(sa.Integer(), primary_key=True, autoincrement=False, index=True)
    nominator_stash = sa.Column(sa.String(64), index=True)
    nominator_controller = sa.Column(sa.String(64), index=True, nullable=True)
    bonded = sa.Column(sa.Numeric(precision=65, scale=0))


class AccountIndex(BaseModel):
    __tablename__ = 'data_account_index'

    id = sa.Column(sa.Integer(), primary_key=True, autoincrement=False)
    short_address = sa.Column(sa.String(24), index=True)
    account_id = sa.Column(sa.String(64), index=True)
    is_reclaimable = sa.Column(sa.Boolean, default=False)
    is_reclaimed = sa.Column(sa.Boolean, default=False)
    created_at_block = sa.Column(sa.Integer(), nullable=False)
    updated_at_block = sa.Column(sa.Integer(), nullable=False)


class AccountIndexAudit(BaseModel):
    __tablename__ = 'data_account_index_audit'

    id = sa.Column(sa.Integer(), primary_key=True, autoincrement=True)
    account_index_id = sa.Column(sa.Integer(), nullable=True, index=True)
    account_id = sa.Column(sa.String(64), index=True, nullable=True)
    block_id = sa.Column(sa.Integer(), index=True, nullable=False)
    extrinsic_idx = sa.Column(sa.Integer())
    event_idx = sa.Column(sa.Integer())
    type_id = sa.Column(sa.Integer(), nullable=False)
    data = sa.Column(sa.JSON(), default=None, server_default=None, nullable=True)


class Contract(BaseModel):
    __tablename__ = 'data_contract'

    code_hash = sa.Column(sa.String(64), primary_key=True)
    bytecode = sa.Column(LONGTEXT())
    source = sa.Column(LONGTEXT())
    abi = sa.Column(sa.JSON(), default=None, server_default=None, nullable=True)
    compiler = sa.Column(sa.String(64))
    created_at_block = sa.Column(sa.Integer(), nullable=False)
    created_at_extrinsic = sa.Column(sa.Integer())
    created_at_event = sa.Column(sa.Integer())


class Runtime(BaseModel):
    __tablename__ = 'runtime'

    serialize_exclude = ['json_metadata', 'json_metadata_decoded']

    id = sa.Column(sa.Integer(), primary_key=True, autoincrement=False)
    impl_name = sa.Column(sa.String(255))
    impl_version = sa.Column(sa.Integer())
    spec_version = sa.Column(sa.Integer(), nullable=False, unique=True)
    spec_name = sa.Column(sa.String(255))
    authoring_version = sa.Column(sa.Integer())
    apis = sa.Column(sa.JSON(), default=None, server_default=None, nullable=True)
    json_metadata = sa.Column(sa.JSON(), default=None, server_default=None, nullable=True)
    json_metadata_decoded = sa.Column(sa.JSON(), default=None, server_default=None, nullable=True)
    count_modules = sa.Column(sa.Integer(), default=0, nullable=False)
    count_call_functions = sa.Column(sa.Integer(), default=0, nullable=False)
    count_storage_functions = sa.Column(sa.Integer(), default=0, nullable=False)
    count_events = sa.Column(sa.Integer(), default=0, nullable=False)
    count_constants = sa.Column(sa.Integer(), nullable=False, server_default='0')
    count_errors = sa.Column(sa.Integer(), nullable=False, server_default='0')

    def serialize_id(self):
        return self.spec_version


class RuntimeModule(BaseModel):
    __tablename__ = 'runtime_module'
    __table_args__ = (sa.UniqueConstraint('spec_version', 'module_id'),)

    id = sa.Column(sa.Integer(), primary_key=True)
    spec_version = sa.Column(sa.Integer(), nullable=False)
    module_id = sa.Column(sa.String(64), nullable=False)
    prefix = sa.Column(sa.String(255))
    # TODO unused?
    code = sa.Column(sa.String(255))
    name = sa.Column(sa.String(255))
    # TODO unused?
    lookup = sa.Column(sa.String(4), index=True)
    count_call_functions = sa.Column(sa.Integer(), nullable=False)
    count_storage_functions = sa.Column(sa.Integer(), nullable=False)
    count_events = sa.Column(sa.Integer(), nullable=False)
    count_constants = sa.Column(sa.Integer(), nullable=False, server_default='0')
    count_errors = sa.Column(sa.Integer(), nullable=False, server_default='0')

    def serialize_id(self):
        return '{}-{}'.format(self.spec_version, self.module_id)


class RuntimeCall(BaseModel):
    __tablename__ = 'runtime_call'
    __table_args__ = (sa.UniqueConstraint('spec_version', 'module_id', 'call_id'),)

    id = sa.Column(sa.Integer(), primary_key=True)
    spec_version = sa.Column(sa.Integer(), nullable=False)
    module_id = sa.Column(sa.String(64), nullable=False)
    call_id = sa.Column(sa.String(64), nullable=False)
    index = sa.Column(sa.Integer(), nullable=False)
    prefix = sa.Column(sa.String(255))
    code = sa.Column(sa.String(255))
    name = sa.Column(sa.String(255))
    lookup = sa.Column(sa.String(4), index=True)
    documentation = sa.Column(sa.Text())
    count_params = sa.Column(sa.Integer(), nullable=False)

    def serialize_id(self):
        return '{}-{}-{}'.format(self.spec_version, self.module_id, self.call_id)


class RuntimeCallParam(BaseModel):
    __tablename__ = 'runtime_call_param'
    __table_args__ = (sa.UniqueConstraint('runtime_call_id', 'name'),)

    id = sa.Column(sa.Integer(), primary_key=True)
    runtime_call_id = sa.Column(sa.Integer(), nullable=False)
    name = sa.Column(sa.String(255))
    type = sa.Column(sa.String(255))


class RuntimeEvent(BaseModel):
    __tablename__ = 'runtime_event'
    __table_args__ = (sa.UniqueConstraint('spec_version', 'module_id', 'event_id'),)

    id = sa.Column(sa.Integer(), primary_key=True)
    spec_version = sa.Column(sa.Integer(), nullable=False)
    module_id = sa.Column(sa.String(64), nullable=False)
    event_id = sa.Column(sa.String(64), nullable=False)
    index = sa.Column(sa.Integer(), nullable=False)
    prefix = sa.Column(sa.String(255))
    code = sa.Column(sa.String(255))
    name = sa.Column(sa.String(255))
    lookup = sa.Column(sa.String(4), index=True)
    documentation = sa.Column(sa.Text())
    count_attributes = sa.Column(sa.Integer(), nullable=False)

    def serialize_id(self):
        return '{}-{}-{}'.format(self.spec_version, self.module_id, self.event_id)


class RuntimeEventAttribute(BaseModel):
    __tablename__ = 'runtime_event_attribute'
    __table_args__ = (sa.UniqueConstraint('runtime_event_id', 'index'),)

    id = sa.Column(sa.Integer(), primary_key=True)
    runtime_event_id = sa.Column(sa.Integer(), nullable=False)
    index = sa.Column(sa.Integer(), nullable=False)
    type = sa.Column(sa.JSON(), default=None, server_default=None)


class RuntimeStorage(BaseModel):
    __tablename__ = 'runtime_storage'

    id = sa.Column(sa.Integer(), primary_key=True)
    spec_version = sa.Column(sa.Integer())
    module_id = sa.Column(sa.String(64))
    storage_key = sa.Column(sa.String(255))
    index = sa.Column(sa.Integer())
    name = sa.Column(sa.String(255))
    lookup = sa.Column(sa.String(4), index=True)
    default = sa.Column(sa.String(255))
    modifier = sa.Column(sa.String(64))
    type_hasher = sa.Column(sa.String(255))
    type_key1 = sa.Column(sa.String(255))
    type_key2 = sa.Column(sa.String(255))
    type_value = sa.Column(sa.String(255))
    type_is_linked = sa.Column(sa.SmallInteger())
    type_key2hasher = sa.Column(sa.String(255))
    documentation = sa.Column(sa.Text())

    def get_return_type(self):
        if self.type_is_linked:
            return '({}, Linkage<AccountId>)'.format(self.type_value)
        else:
            return self.type_value

    def serialize_id(self):
        return '{}-{}-{}'.format(self.spec_version, self.module_id, self.name)

    def get_types(self):
        r = []
        if self.type_key1 is not None:
            r = [self.type_key1]
        if self.type_key2 is not None:
            r.append(self.type_key2)
        return r

    def get_hashers(self):
        r = []
        if self.type_hasher is not None:
            r = [self.type_hasher]
        if self.type_key2hasher is not None:
            r.append(self.type_key2hasher)
        return r


class RuntimeConstant(BaseModel):
    __tablename__ = 'runtime_constant'

    id = sa.Column(sa.Integer(), primary_key=True)
    spec_version = sa.Column(sa.Integer())
    module_id = sa.Column(sa.String(64))
    index = sa.Column(sa.Integer())
    name = sa.Column(sa.String(255), index=True)
    type = sa.Column(sa.String(255))
    # value = sa.Column(sa.String(255))
    value = sa.Column(sa.Text())
    documentation = sa.Column(sa.Text())

    def serialize_id(self):
        return '{}-{}-{}'.format(self.spec_version, self.module_id, self.name)


class RuntimeErrorMessage(BaseModel):
    __tablename__ = 'runtime_error'

    id = sa.Column(sa.Integer(), primary_key=True)
    spec_version = sa.Column(sa.Integer())
    module_id = sa.Column(sa.String(64))
    module_index = sa.Column(sa.Integer())
    index = sa.Column(sa.Integer())
    name = sa.Column(sa.String(255), index=True)
    documentation = sa.Column(sa.Text())

    def serialize_id(self):
        return '{}-{}-{}'.format(self.spec_version, self.module_id, self.index)


class RuntimeType(BaseModel):
    __tablename__ = 'runtime_type'
    __table_args__ = (sa.UniqueConstraint('spec_version', 'type_string'),)

    id = sa.Column(sa.Integer(), primary_key=True)
    spec_version = sa.Column(sa.Integer(), nullable=False)
    type_string = sa.Column(sa.String(255))
    decoder_class = sa.Column(sa.String(255), nullable=True)
    is_primitive_runtime = sa.Column(sa.Boolean(), default=False)
    is_primitive_core = sa.Column(sa.Boolean(), default=False)


class ReorgBlock(BaseModel):
    __tablename__ = 'data_reorg_block'

    serialize_exclude = ['debug_info']

    hash = sa.Column(sa.String(66), primary_key=True, index=True, nullable=False)
    id = sa.Column(sa.Integer(), index=True, autoincrement=False)
    parent_id = sa.Column(sa.Integer(), nullable=False)
    parent_hash = sa.Column(sa.String(66), index=True, nullable=False)
    state_root = sa.Column(sa.String(66), nullable=False)
    extrinsics_root = sa.Column(sa.String(66), nullable=False)
    count_extrinsics = sa.Column(sa.Integer(), nullable=False)
    count_extrinsics_unsigned = sa.Column(sa.Integer(), nullable=False)
    count_extrinsics_signed = sa.Column(sa.Integer(), nullable=False)
    count_extrinsics_error = sa.Column(sa.Integer(), nullable=False)
    count_extrinsics_success = sa.Column(sa.Integer(), nullable=False)
    count_extrinsics_signedby_address = sa.Column(sa.Integer(), nullable=False)
    count_extrinsics_signedby_index = sa.Column(sa.Integer(), nullable=False)
    count_events = sa.Column(sa.Integer(), nullable=False)
    count_events_system = sa.Column(sa.Integer(), nullable=False)
    count_events_module = sa.Column(sa.Integer(), nullable=False)
    count_events_transfer = sa.Column(sa.Integer(), nullable=False)
    count_events_extrinsic = sa.Column(sa.Integer(), nullable=False)
    count_events_finalization = sa.Column(sa.Integer(), nullable=False)
    count_accounts = sa.Column(sa.Integer(), nullable=False)
    count_accounts_new = sa.Column(sa.Integer(), nullable=False)
    count_accounts_reaped = sa.Column(sa.Integer(), nullable=False)
    count_sessions_new = sa.Column(sa.Integer(), nullable=False)
    count_contracts_new = sa.Column(sa.Integer(), nullable=False)
    count_log = sa.Column(sa.Integer(), nullable=False)
    range10000 = sa.Column(sa.Integer(), nullable=False)
    range100000 = sa.Column(sa.Integer(), nullable=False)
    range1000000 = sa.Column(sa.Integer(), nullable=False)
    datetime = sa.Column(sa.DateTime(timezone=True))
    year = sa.Column(sa.Integer(), nullable=True)
    month = sa.Column(sa.Integer(), nullable=True)
    week = sa.Column(sa.Integer(), nullable=True)
    day = sa.Column(sa.Integer(), nullable=True)
    hour = sa.Column(sa.Integer(), nullable=True)
    full_month = sa.Column(sa.Integer(), nullable=True)
    full_week = sa.Column(sa.Integer(), nullable=True)
    full_day = sa.Column(sa.Integer(), nullable=True)
    full_hour = sa.Column(sa.Integer(), nullable=True)
    logs = sa.Column(sa.JSON(), default=None, server_default=None)
    authority_index = sa.Column(sa.Integer(), nullable=True)
    slot_number = sa.Column(sa.Numeric(precision=65, scale=0), nullable=True)
    spec_version_id = sa.Column(sa.String(64), nullable=False)
    debug_info = sa.Column(sa.JSON(), default=None, server_default=None)


class ReorgEvent(BaseModel):
    __tablename__ = 'data_reorg_event'

    block_hash = sa.Column(sa.String(66), primary_key=True, index=True, nullable=False)
    block_id = sa.Column(sa.Integer(), index=True)
    block = relationship(Block, foreign_keys=[block_id], primaryjoin=block_id == Block.id)

    event_idx = sa.Column(sa.Integer(), primary_key=True, index=True)

    extrinsic_idx = sa.Column(sa.Integer(), index=True)

    type = sa.Column(sa.String(4), index=True)

    spec_version_id = sa.Column(sa.Integer())

    module_id = sa.Column(sa.String(64), index=True)
    event_id = sa.Column(sa.String(64), index=True)

    system = sa.Column(sa.SmallInteger(), index=True, nullable=False)
    module = sa.Column(sa.SmallInteger(), index=True, nullable=False)
    phase = sa.Column(sa.SmallInteger())

    attributes = sa.Column(sa.JSON())

    codec_error = sa.Column(sa.Boolean())

    def serialize_id(self):
        return '{}-{}'.format(self.block_id, self.event_idx)


class ReorgExtrinsic(BaseModel):
    __tablename__ = 'data_reorg_extrinsic'

    block_hash = sa.Column(sa.String(66), primary_key=True, index=True, nullable=False)
    block_id = sa.Column(sa.Integer(), index=True)
    block = relationship(Block, foreign_keys=[block_id], primaryjoin=block_id == Block.id)

    extrinsic_idx = sa.Column(sa.Integer(), primary_key=True, index=True)
    extrinsic_hash = sa.Column(sa.String(64), index=True, nullable=True)

    extrinsic_length = sa.Column(sa.String(10))
    extrinsic_version = sa.Column(sa.String(2))

    signed = sa.Column(sa.SmallInteger(), index=True, nullable=False)
    unsigned = sa.Column(sa.SmallInteger(), index=True, nullable=False)
    signedby_address = sa.Column(sa.SmallInteger(), nullable=False)
    signedby_index = sa.Column(sa.SmallInteger(), nullable=False)

    address_length = sa.Column(sa.String(2))
    address = sa.Column(sa.String(64), index=True)
    account_index = sa.Column(sa.String(16), index=True)
    account_idx = sa.Column(sa.Integer(), index=True)
    signature = sa.Column(sa.String(130))
    nonce = sa.Column(sa.Integer())

    era = sa.Column(sa.String(4))

    call = sa.Column(sa.String(4))
    module_id = sa.Column(sa.String(64), index=True)
    call_id = sa.Column(sa.String(64), index=True)
    params = sa.Column(sa.JSON())

    success = sa.Column(sa.SmallInteger(), default=0, nullable=False)
    error = sa.Column(sa.SmallInteger(), default=0, nullable=False)

    spec_version_id = sa.Column(sa.Integer())

    codec_error = sa.Column(sa.Boolean(), default=False)

    def serialize_id(self):
        return '{}-{}'.format(self.block_id, self.extrinsic_idx)


class ReorgLog(BaseModel):
    __tablename__ = 'data_reorg_log'

    block_hash = sa.Column(sa.String(66), primary_key=True, index=True, nullable=False)
    block_id = sa.Column(sa.Integer(), autoincrement=False)
    log_idx = sa.Column(sa.Integer(), primary_key=True, autoincrement=False)
    type_id = sa.Column(sa.Integer(), index=True)
    type = sa.Column(sa.String(64))
    data = sa.Column(sa.JSON())

    def serialize_id(self):
        return '{}-{}'.format(self.block_id, self.log_idx)


class IdentityAudit(BaseModel):
    __tablename__ = 'data_identity_audit'

    id = sa.Column(sa.Integer(), primary_key=True, autoincrement=True)
    account_id = sa.Column(sa.String(64))
    block_id = sa.Column(sa.Integer(), index=True, nullable=False)
    extrinsic_idx = sa.Column(sa.Integer())
    event_idx = sa.Column(sa.Integer())
    type_id = sa.Column(sa.Integer(), nullable=False)
    data = sa.Column(sa.JSON(), default=None, server_default=None, nullable=True)


class IdentityJudgement(BaseModel):
    __tablename__ = 'data_identity_judgement'

    registrar_index = sa.Column(sa.Integer(), primary_key=True)
    account_id = sa.Column(sa.String(64), primary_key=True, index=True)
    judgement = sa.Column(sa.String(32))
    created_at_block = sa.Column(sa.Integer(), nullable=False)
    updated_at_block = sa.Column(sa.Integer(), nullable=False)


class IdentityJudgementAudit(BaseModel):
    __tablename__ = 'data_identity_judgement_audit'

    id = sa.Column(sa.Integer(), primary_key=True, autoincrement=True)
    registrar_index = sa.Column(sa.Integer())
    account_id = sa.Column(sa.String(64))
    block_id = sa.Column(sa.Integer(), index=True, nullable=False)
    extrinsic_idx = sa.Column(sa.Integer())
    event_idx = sa.Column(sa.Integer())
    type_id = sa.Column(sa.Integer(), nullable=False)
    data = sa.Column(sa.JSON(), default=None, server_default=None, nullable=True)


class SearchIndexType(BaseModel):
    __tablename__ = 'data_account_search_index_type'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(64), nullable=False, index=True)


class SearchIndex(BaseModel):
    __tablename__ = 'data_account_search_index'

    id = sa.Column(sa.Integer(), primary_key=True, autoincrement=True)
    block_id = sa.Column(sa.Integer(), nullable=False, index=True)
    extrinsic_idx = sa.Column(sa.Integer(), nullable=True, index=True)
    event_idx = sa.Column(sa.Integer(), nullable=True, index=True)
    account_id = sa.Column(sa.String(64), nullable=True, index=True)
    index_type_id = sa.Column(sa.Integer(), nullable=False, index=True)
    sorting_value = sa.Column(sa.Numeric(precision=65, scale=0), nullable=True, index=True)


class SymbolSnapshot(BaseModel):
    __tablename__ = 'data_symbol_snapshot'

    block_id = sa.Column(sa.Integer(), primary_key=True, index=True)
    symbol = sa.Column(sa.String(30), primary_key=True, index=True)

    price = sa.Column(sa.Integer, nullable=False)
    fraction = sa.Column(sa.Integer, nullable=False)
    auth = sa.Column(sa.JSON(), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=True) # self.block.datetime


class EraPriceRequest(BaseModel):
    __tablename__ = 'data_era_price_request'

    id = sa.Column(sa.Integer(), primary_key=True)
    # era = sa.Column(sa.Integer(), primary_key=True)
    era = sa.Column(sa.Integer(), unique=True)
    total_eras = sa.Column(sa.Integer(), nullable=False)
    era_total_requests = sa.Column(sa.Integer(), nullable=False)
    era_total_points = sa.Column(sa.Integer(), nullable=False)
    era_total_fee = sa.Column(sa.Numeric(precision=65, scale=0), nullable=False)
    ended_at = sa.Column(sa.Integer(), nullable=True)

class ValidatorAuditFromChain(BaseModel):
    __tablename__ = 'data_validator_audit_from_chain'
    id = sa.Column(sa.Integer(), primary_key=True)
    validator = sa.Column(sa.String(100), nullable=False)
    ares_authority = sa.Column(sa.String(100), nullable=False)
    block_number = sa.Column(sa.Integer(), nullable=False)
    status = sa.Column(sa.String(20), nullable=False)
    __table_args__ = (UniqueConstraint('validator', 'ares_authority', name='unqiue_validator_ares_authority'),)


class PriceRequest(BaseModel):
    __tablename__ = 'data_price_request'
    order_id = sa.Column(sa.String(length=100), primary_key=True)
    created_by = sa.Column(sa.String(length=64), nullable=True, index=True)
    symbols = sa.Column(sa.JSON(), nullable=True)
    status = sa.Column(sa.Integer(), nullable=True)  # 0: pending,  1: successful, 2: failed
    prepayment = sa.Column(sa.Numeric(precision=65, scale=0), nullable=True)
    payment = sa.Column(sa.Numeric(precision=65, scale=0), nullable=True)
    auth = sa.Column(sa.JSON(), nullable=True)
    result = sa.Column(sa.JSON(), nullable=True)
    created_at = sa.Column(sa.Integer(), nullable=True, index=True)
    ended_at = sa.Column(sa.Integer(), nullable=True)


class KamiTest(BaseModel):
    __tablename__ = 'data_kami_test'

    id = sa.Column(sa.Integer(), primary_key=True)
    created_at = sa.Column(sa.Integer(), nullable=True, index=True)
    ended_at = sa.Column(sa.Integer(), nullable=True)


class DataReminder(BaseModel):
    __tablename__ = 'data_reminder'

    id = sa.Column('id', sa.Integer(),  primary_key=True, nullable=False)
    reminder_id = sa.Column('reminder_id', sa.Integer, nullable=False)
    owner = sa.Column('owner', sa.String(length=100), nullable=False, index=True)
    owner_ss58 = sa.Column(sa.String(48), index=True)
    interval_bn = sa.Column('interval_bn', sa.Integer(), nullable=False)
    repeat_count = sa.Column('repeat_count', sa.Integer(), nullable=False)
    create_bn = sa.Column('create_bn', sa.Integer(), nullable=False)
    price_snapshot = sa.Column('price_snapshot', sa.Float(), nullable=False)
    trigger_condition_type = sa.Column('trigger_condition_type', sa.String(length=100), nullable=False)
    trigger_condition_price_key = sa.Column('trigger_condition_price_key', sa.String(length=100), nullable=False)
    anchor_price = sa.Column('anchor_price', sa.Float(), nullable=False)
    trigger_receiver_type = sa.Column('trigger_receiver_type', sa.String(length=100), nullable=False)
    trigger_receiver_url = sa.Column('trigger_receiver_url', sa.String(length=512), nullable=False)
    trigger_receiver_sign = sa.Column('trigger_receiver_sign', sa.String(length=256), nullable=False)
    update_bn = sa.Column('update_bn', sa.Integer(), nullable=False)
    tip = sa.Column('tip', sa.String(length=256), nullable=False)
    block_id = sa.Column('block_id', sa.Integer(), nullable=False, index=True)
    datetime = sa.Column('datetime', sa.DateTime(timezone=True), nullable=True)

class DataReminderMsg(BaseModel):
    __tablename__ = 'data_reminder_msg'

    id = sa.Column('id', sa.Integer(), primary_key=True, nullable=False)
    reminder_id = sa.Column('reminder_id', sa.Integer, nullable=False)
    remaining_count = sa.Column('remaining_count', sa.Integer, nullable=False)
    send_bn = sa.Column('send_bn', sa.Integer(), nullable=False)
    submitter = sa.Column('submitter', sa.String(length=100), nullable=False, index=True)
    response_mark = sa.Column('response_mark', sa.String(length=64), nullable=True)
    status = sa.Column('status', sa.Integer(), nullable=True, index=True)
    block_id = sa.Column('block_id', sa.Integer(), nullable=False, index=True)
    datetime = sa.Column('datetime', sa.DateTime(timezone=True), nullable=True)

class DataReminderLifecycle(BaseModel):
    __tablename__ = 'data_reminder_lifecycle'

    id = sa.Column('id', sa.Integer(), primary_key=True, nullable=False)
    reminder_id = sa.Column('reminder_id', sa.Integer, nullable=False, index=True)
    points = sa.Column('points', sa.Integer, nullable=False, index=True)
    is_released = sa.Column('is_released', sa.Integer, nullable=True, index=True)
    # owner = sa.Column('owner', sa.String(length=100), nullable=True, index=True)
    # owner_ss58 = sa.Column('owner_ss58', sa.String(length=48), nullable=True, index=True)

class EstimatesParticipants(BaseModel):
    __tablename__ = 'data_estimates_participants'
    symbol = sa.Column(sa.String(length=30), primary_key=True, nullable=False)
    estimate_id = sa.Column(sa.Integer(), primary_key=True, nullable=False)
    estimate_type = sa.Column(sa.String(length=30), primary_key=True, nullable=False, index=True)
    participant = sa.Column(sa.String(length=64), primary_key=True, nullable=False)
    ss58_address = sa.Column(sa.String(48), index=True)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=True)  # self.block.datetime
    price = sa.Column(sa.Numeric(precision=65, scale=0), nullable=True)
    deposit = sa.Column(sa.Numeric(precision=65, scale=0), nullable=True)
    option_index = sa.Column(sa.Integer(), nullable=True)
    end = sa.Column(sa.Integer(), nullable=False)
    block_id = sa.Column(sa.Integer(), nullable=False)

class EstimatesDataList(BaseModel):
    __tablename__ = 'data_estimates_list'
    id = sa.Column(sa.Integer(), primary_key=True, autoincrement=True)
    estimate_id = sa.Column(sa.Integer(), primary_key=True, nullable=False)
    symbol = sa.Column(sa.String(length=30), primary_key=True, nullable=False)
    symbol_fraction = sa.Column(sa.Integer(), nullable=False)
    state = sa.Column(sa.String(length=16), primary_key=True, nullable=False, index=True) # InActive
    start = sa.Column(sa.Integer(), nullable=False) # 1068200
    end = sa.Column(sa.Integer(), nullable=False)
    distribute = sa.Column(sa.Integer(), nullable=False)
    range_data = sa.Column(LONGTEXT()) # range
    deviation = sa.Column(sa.Numeric(precision=65, scale=0), nullable=True, index=True)
    multiplier = sa.Column(LONGTEXT())
    ticket_price = sa.Column(sa.Numeric(precision=65, scale=0), nullable=True, index=True)
    estimates_type = sa.Column(sa.String(length=30), primary_key=True, nullable=False, index=True)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    block_id = sa.Column(sa.Integer(), nullable=False)
    symbol_completed_price = sa.Column(sa.Numeric(precision=65, scale=0), nullable=True, index=True)
    total_reward = sa.Column(sa.Numeric(precision=65, scale=0), nullable=True, index=True)

    def fill_data(self, attributes, block, event):
        estimate_id = attributes['id']
        estimate_symbol = attributes['symbol']
        estimates_type = attributes['estimates_type']
        estimates_ticket_price = attributes['ticket_price']
        estimates_symbol_completed_price = attributes['symbol_completed_price']
        estimates_symbol_fraction = attributes['symbol_fraction']
        estimates_start = attributes['start']
        estimates_end = attributes['end']
        estimates_distribute = attributes['distribute']
        estimates_multiplier = attributes['multiplier']
        estimates_deviation = attributes['deviation']
        estimates_range = attributes['range']
        estimates_total_reward = attributes['total_reward']
        estimates_state = attributes['state']
        estimates_created_at = None
        if block:
            estimates_created_at = block.datetime

        estimates_block_id = None
        if event:
            estimates_block_id = event.block_id

        # print(estimate_id, '-#-', estimate_symbol, '-#-', estimates_type, '-#-', estimates_ticket_price, '-#-',
        #       estimates_symbol_completed_price, '-#-', estimates_symbol_fraction, '-#-', estimates_start, '-#-',
        #       estimates_end, '-#-', estimates_distribute, '-#-', estimates_multiplier, '-#-', estimates_deviation,
        #       '-#-',
        #       estimates_range, '-#-', estimates_total_reward, '-#-', estimates_state)

        return EstimatesDataList(
            estimate_id=estimate_id,
            symbol=estimate_symbol,
            symbol_fraction=estimates_symbol_fraction,
            state=estimates_state,
            start=estimates_start,
            end=estimates_end,
            distribute=estimates_distribute,
            range_data=str(estimates_range),
            deviation=estimates_deviation,
            multiplier=str(estimates_multiplier),
            ticket_price=estimates_ticket_price,
            estimates_type=estimates_type,
            created_at=estimates_created_at,
            block_id=estimates_block_id,
            symbol_completed_price=estimates_symbol_completed_price,
            total_reward=estimates_total_reward,
        )

class EstimatesWinner(BaseModel):
    __tablename__ = 'data_estimates_winner'
    id = sa.Column(sa.Integer(), primary_key=True, autoincrement=True)
    block_id = sa.Column('block_id', sa.Integer(), nullable=False)
    symbol = sa.Column('symbol', sa.String(length=30), nullable=False)
    estimate_id = sa.Column('estimate_id', sa.Integer(), nullable=False)
    estimate_type = sa.Column('estimate_type', sa.String(length=30), nullable=False)
    ss58_address = sa.Column('ss58_address', sa.String(length=48), nullable=False)
    public_key = sa.Column('public_key', sa.String(length=64), nullable=False)
    reward = sa.Column('reward', sa.Numeric(precision=65, scale=0), nullable=False)
    created_at = sa.Column('created_at', sa.DateTime(timezone=True), nullable=True)
