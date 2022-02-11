"""upgrade dependencies

Revision ID: e5bd0b0f689b
Revises: e627476917aa
Create Date: 2021-12-02 17:41:32.223887

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'e5bd0b0f689b'
down_revision = 'e627476917aa'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index('ix_data_session_validator_validator_session', table_name='data_session_validator')
    op.alter_column('data_extrinsic', 'era',
                    existing_type=mysql.VARCHAR(length=4),
                    type_=mysql.VARCHAR(length=20),
                    existing_nullable=True)
    op.alter_column('data_reorg_extrinsic', 'era',
                    existing_type=mysql.VARCHAR(length=4),
                    type_=mysql.VARCHAR(length=20),
                    existing_nullable=True)
    op.alter_column('runtime_event_attribute', 'type',
                    existing_type=mysql.VARCHAR(length=255),
                    type_=mysql.JSON,
                    existing_nullable=True)
    op.alter_column('data_session_validator', 'validator_session',
                    existing_type=mysql.VARCHAR(length=64),
                    type_=mysql.JSON,
                    existing_nullable=True)
    op.add_column('data_block', sa.Column('count_events_transfer', sa.Integer(), nullable=False))
    op.add_column('data_reorg_block', sa.Column('count_events_transfer', sa.Integer(), nullable=False))
    op.add_column('data_block_total',
                  sa.Column('total_events_transfer', sa.Numeric(precision=65, scale=0), nullable=False))
    op.add_column('data_block_total',
                  sa.Column('total_treasury_burn', sa.Numeric(precision=65, scale=0), nullable=False))

def downgrade():
    op.alter_column('data_extrinsic', 'era',
                    existing_type=mysql.VARCHAR(length=20),
                    type_=mysql.VARCHAR(length=4),
                    existing_nullable=True)
    op.alter_column('data_reorg_extrinsic', 'era',
                    existing_type=mysql.VARCHAR(length=20),
                    type_=mysql.VARCHAR(length=4),
                    existing_nullable=True)
    op.alter_column('runtime_event_attribute', 'type',
                    existing_type=mysql.JSON,
                    type_=mysql.VARCHAR(length=255),
                    existing_nullable=True)

    op.alter_column('data_session_validator', 'validator_session',
                    existing_type=mysql.JSON,
                    type_=mysql.VARCHAR(length=64),
                    existing_nullable=True)

    op.create_index(op.f('ix_data_session_validator_validator_session'), 'data_session_validator',
                    ['validator_session'], unique=False)

    op.drop_column('data_block', 'count_events_transfer')
    op.drop_column('data_reorg_block', 'count_events_transfer')
    op.drop_column('data_block_total', 'total_events_transfer')
    op.drop_column('data_block_total', 'total_treasury_burn')
