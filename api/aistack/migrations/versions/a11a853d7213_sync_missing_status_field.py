"""sync missing status field

Revision ID: a11a853d7213
Revises: 4c22566601b7
Create Date: 2025-07-13 11:08:57.401968

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = 'a11a853d7213'
down_revision: Union[str, None] = '4c22566601b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('app_instances')
    op.drop_index(op.f('ix_apps_name'), table_name='apps')
    op.drop_table('apps')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('apps',
    sa.Column('deleted_at', sa.DATETIME(), nullable=True),
    sa.Column('name', sa.VARCHAR(), nullable=False),
    sa.Column('display_name', sa.VARCHAR(), nullable=False),
    sa.Column('description', sa.TEXT(), nullable=True),
    sa.Column('app_type', sa.VARCHAR(), nullable=False),
    sa.Column('image_source', sa.VARCHAR(), nullable=False),
    sa.Column('dockerfile_path', sa.VARCHAR(), nullable=True),
    sa.Column('image_name', sa.VARCHAR(), nullable=False),
    sa.Column('image_url', sa.VARCHAR(), nullable=True),
    sa.Column('image_tag', sa.VARCHAR(), nullable=False),
    sa.Column('container_name', sa.VARCHAR(), nullable=True),
    sa.Column('ports', sqlite.JSON(), nullable=True),
    sa.Column('environment', sqlite.JSON(), nullable=True),
    sa.Column('volumes', sqlite.JSON(), nullable=True),
    sa.Column('urls', sqlite.JSON(), nullable=True),
    sa.Column('memory_limit', sa.VARCHAR(), nullable=True),
    sa.Column('cpu_limit', sa.VARCHAR(), nullable=True),
    sa.Column('tags', sqlite.JSON(), nullable=True),
    sa.Column('category', sa.VARCHAR(), nullable=True),
    sa.Column('version', sa.VARCHAR(), nullable=True),
    sa.Column('is_active', sa.BOOLEAN(), nullable=False),
    sa.Column('is_preset', sa.BOOLEAN(), nullable=False),
    sa.Column('build_status', sa.VARCHAR(), nullable=True),
    sa.Column('build_message', sa.TEXT(), nullable=True),
    sa.Column('build_started_at', sa.DATETIME(), nullable=True),
    sa.Column('build_finished_at', sa.DATETIME(), nullable=True),
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.Column('updated_at', sa.DATETIME(), nullable=False),
    sa.Column('status', sa.VARCHAR(length=50), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_apps_name'), 'apps', ['name'], unique=False)
    op.create_table('app_instances',
    sa.Column('deleted_at', sa.DATETIME(), nullable=True),
    sa.Column('app_id', sa.INTEGER(), nullable=False),
    sa.Column('container_id', sa.VARCHAR(), nullable=True),
    sa.Column('status', sa.VARCHAR(), nullable=False),
    sa.Column('status_message', sa.TEXT(), nullable=True),
    sa.Column('started_at', sa.DATETIME(), nullable=True),
    sa.Column('stopped_at', sa.DATETIME(), nullable=True),
    sa.Column('memory_usage', sa.VARCHAR(), nullable=True),
    sa.Column('cpu_usage', sa.FLOAT(), nullable=True),
    sa.Column('ip_address', sa.VARCHAR(), nullable=True),
    sa.Column('exposed_ports', sqlite.JSON(), nullable=True),
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.Column('updated_at', sa.DATETIME(), nullable=False),
    sa.ForeignKeyConstraint(['app_id'], ['apps.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###
