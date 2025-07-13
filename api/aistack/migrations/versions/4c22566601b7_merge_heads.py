"""merge heads

Revision ID: 4c22566601b7
Revises: add_status_field_to_apps, merge_heads_001
Create Date: 2025-07-13 10:51:41.993581

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c22566601b7'
down_revision: Union[str, None] = ('add_status_field_to_apps', 'merge_heads_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
