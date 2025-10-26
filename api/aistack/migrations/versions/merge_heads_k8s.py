"""Merge all heads

Revision ID: merge_heads_k8s
Revises: 001, 0c73bbbd778c, add_user_app_relationship, k8s_apps_001
Create Date: 2025-10-26 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'merge_heads_k8s'
down_revision: Union[str, None] = ('001', '0c73bbbd778c', 'add_user_app_relationship', 'k8s_apps_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This is a merge migration, no actual changes needed
    pass


def downgrade() -> None:
    # This is a merge migration, no actual changes needed
    pass
