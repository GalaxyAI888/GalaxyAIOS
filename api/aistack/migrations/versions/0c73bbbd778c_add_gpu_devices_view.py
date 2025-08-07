"""add_gpu_devices_view

Revision ID: 0c73bbbd778c
Revises: a11a853d7213
Create Date: 2025-08-06 17:20:16.428445

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0c73bbbd778c'
down_revision: Union[str, None] = 'a11a853d7213'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None





# 在upgrade()函数中添加
def upgrade() -> None:
    # 创建GPU设备视图
    op.execute("""
    CREATE VIEW IF NOT EXISTS gpu_devices_view AS
    SELECT
        'local:' || json_extract(value, '$.type') || ':' || json_extract(value, '$.index') AS id,
        1 as worker_id,
        'local' as worker_name,
        '127.0.0.1' as worker_ip,
        datetime('now') as created_at,
        datetime('now') as updated_at,
        NULL as deleted_at,
        json_extract(value, '$.uuid') AS uuid,
        json_extract(value, '$.name') AS name,
        json_extract(value, '$.vendor') AS vendor,
        json_extract(value, '$.index') AS 'index',
        json_extract(value, '$.device_index') AS 'device_index',
        json_extract(value, '$.device_chip_index') AS 'device_chip_index',
        json_extract(value, '$.core') AS core,
        json_extract(value, '$.memory') AS memory,
        json_extract(value, '$.network') AS network,
        json_extract(value, '$.temperature') AS temperature,
        json_extract(value, '$.labels') AS labels,
        json_extract(value, '$.type') AS type
    FROM
        (SELECT json('[]') as gpu_devices)
    """)

def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS gpu_devices_view")
