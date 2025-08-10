"""Add User-App relationship

Revision ID: add_user_app_relationship
Revises: add_app_management_tables
Create Date: 2025-01-21 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_user_app_relationship'
down_revision: Union[str, None] = 'add_app_management_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 添加 user_id 字段到 apps 表
    op.add_column('apps', sa.Column('user_id', sa.Integer(), nullable=True))
    
    # 添加外键约束
    op.create_foreign_key(
        'fk_apps_user_id_users',
        'apps', 'users',
        ['user_id'], ['id']
    )
    
    # 创建索引以提高查询性能
    op.create_index(op.f('ix_apps_user_id'), 'apps', ['user_id'], unique=False)


def downgrade() -> None:
    # 删除索引
    op.drop_index(op.f('ix_apps_user_id'), table_name='apps')
    
    # 删除外键约束
    op.drop_constraint('fk_apps_user_id_users', 'apps', type_='foreignkey')
    
    # 删除 user_id 字段
    op.drop_column('apps', 'user_id')
