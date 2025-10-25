"""add k8s fields to apps

Revision ID: 001
Revises: 
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """添加Kubernetes相关字段到apps表"""
    # 添加Kubernetes相关字段
    op.add_column('apps', sa.Column('deployment_yaml_url', sa.String(), nullable=True))
    op.add_column('apps', sa.Column('service_yaml_url', sa.String(), nullable=True))
    op.add_column('apps', sa.Column('config_yaml_url', sa.String(), nullable=True))
    op.add_column('apps', sa.Column('ingress_yaml_url', sa.String(), nullable=True))


def downgrade():
    """移除Kubernetes相关字段"""
    op.drop_column('apps', 'ingress_yaml_url')
    op.drop_column('apps', 'config_yaml_url')
    op.drop_column('apps', 'service_yaml_url')
    op.drop_column('apps', 'deployment_yaml_url')

