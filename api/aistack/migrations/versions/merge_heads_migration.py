"""merge heads migration

Revision ID: merge_heads_001
Revises: 075c2de47b2a, 431ec0706ef1, 681896eec5fc, add_app_management_tables
Create Date: 2024-07-05 10:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = 'merge_heads_001'
down_revision = ('075c2de47b2a', '431ec0706ef1', '681896eec5fc', 'add_app_management_tables')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 这是一个合并迁移，不需要执行任何操作
    # 所有表结构已经在各个分支迁移中创建
    pass


def downgrade() -> None:
    # 这是一个合并迁移，不需要执行任何操作
    pass 