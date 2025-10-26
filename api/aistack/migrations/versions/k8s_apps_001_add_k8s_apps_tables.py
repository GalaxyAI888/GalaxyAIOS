"""Add k8s_apps tables

Revision ID: k8s_apps_001
Revises: 4c22566601b7
Create Date: 2025-10-26 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'k8s_apps_001'
down_revision: Union[str, None] = '4c22566601b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create k8s_apps table
    op.create_table('k8s_apps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('icon', sa.String(length=500), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('dockerfile', sa.String(length=500), nullable=True),
        sa.Column('docker_img_url', sa.String(length=500), nullable=True),
        sa.Column('img_name', sa.String(length=255), nullable=True),
        sa.Column('img_tag', sa.String(length=100), nullable=False),
        sa.Column('imgsize', sa.String(length=50), nullable=True),
        sa.Column('deployment', sa.Text(), nullable=True),
        sa.Column('service', sa.Text(), nullable=True),
        sa.Column('configmap', sa.Text(), nullable=True),
        sa.Column('ingress', sa.Text(), nullable=True),
        sa.Column('app_type', sa.Enum('WEB_APP', 'API_SERVICE', 'MICROSERVICE', 'WORKLOAD', name='k8sapptypeenum'), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('status', sa.Enum('STOPPED', 'DEPLOYING', 'RUNNING', 'ERROR', 'UPDATING', 'SCALING', 'DELETING', name='k8sappstatusenum'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_preset', sa.Boolean(), nullable=False),
        sa.Column('namespace', sa.String(length=100), nullable=False),
        sa.Column('replicas', sa.Integer(), nullable=False),
        sa.Column('status_message', sa.Text(), nullable=True),
        sa.Column('deployed_at', sa.DateTime(), nullable=True),
        sa.Column('last_updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_k8s_apps_name'), 'k8s_apps', ['name'], unique=True)
    op.create_index(op.f('ix_k8s_apps_user_id'), 'k8s_apps', ['user_id'], unique=False)

    # Create k8s_app_instances table
    op.create_table('k8s_app_instances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('k8s_app_id', sa.Integer(), nullable=False),
        sa.Column('pod_name', sa.String(length=255), nullable=True),
        sa.Column('status', sa.Enum('STOPPED', 'DEPLOYING', 'RUNNING', 'ERROR', 'UPDATING', 'SCALING', 'DELETING', name='k8sappstatusenum'), nullable=False),
        sa.Column('status_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('stopped_at', sa.DateTime(), nullable=True),
        sa.Column('memory_usage', sa.String(length=50), nullable=True),
        sa.Column('cpu_usage', sa.Float(), nullable=True),
        sa.Column('pod_ip', sa.String(length=50), nullable=True),
        sa.Column('node_name', sa.String(length=255), nullable=True),
        sa.Column('deployment_name', sa.String(length=255), nullable=True),
        sa.Column('service_name', sa.String(length=255), nullable=True),
        sa.Column('namespace', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['k8s_app_id'], ['k8s_apps.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_k8s_app_instances_k8s_app_id'), 'k8s_app_instances', ['k8s_app_id'], unique=False)


def downgrade() -> None:
    # Drop k8s_app_instances table
    op.drop_index(op.f('ix_k8s_app_instances_k8s_app_id'), table_name='k8s_app_instances')
    op.drop_table('k8s_app_instances')
    
    # Drop k8s_apps table
    op.drop_index(op.f('ix_k8s_apps_user_id'), table_name='k8s_apps')
    op.drop_index(op.f('ix_k8s_apps_name'), table_name='k8s_apps')
    op.drop_table('k8s_apps')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS k8sappstatusenum")
    op.execute("DROP TYPE IF EXISTS k8sapptypeenum")
