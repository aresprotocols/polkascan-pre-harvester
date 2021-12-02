"""upgrade dependencies

Revision ID: 3b40c1445b1b
Revises: e627476917aa
Create Date: 2021-12-02 17:43:05.076157

"""
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '3b40c1445b1b'
down_revision = 'e627476917aa'
branch_labels = None
depends_on = None


def upgrade():
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
