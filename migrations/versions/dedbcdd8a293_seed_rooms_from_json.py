"""seed rooms from json

Revision ID: dedbcdd8a293
Revises: 57203c6465eb
Create Date: 2025-11-03 10:20:14.300488

"""
from alembic import op
import sqlalchemy as sa
import json
import os
from datetime import datetime, timezone

revision = 'dedbcdd8a293'
down_revision = '57203c6465eb'  
branch_labels = None
depends_on = None

def upgrade():
    json_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        '..',
        'data', 
        'rooms.json'
    )
    json_path = os.path.abspath(json_path)
    with open(json_path, 'r') as f:
        rooms_data = json.load(f)
    connection = op.get_bind()
    meta = sa.MetaData()
    meta.reflect(bind=connection)
    room_table = meta.tables['room']
    now = datetime.now(timezone.utc)
    for room in rooms_data:
        result = connection.execute(
            sa.select(room_table.c.id).where(room_table.c.id == room['id'])
        ).first()
        if not result:
            connection.execute(
                room_table.insert().values(
                    id=room['id'],
                    name=room['name'],
                    description=room['description'],
                    price=room['price'],
                    created_at=now,
                    updated_at=now
                )
            )

def downgrade():
    connection = op.get_bind()
    meta = sa.MetaData()
    meta.reflect(bind=connection)
    room_table = meta.tables['room']
    json_path = os.path.join(
        os.path.dirname(__file__),
        '..',
        '..',
        'data',
        'rooms.json'
    )
    json_path = os.path.abspath(json_path)
    with open(json_path, 'r') as f:
        rooms_data = json.load(f)
    room_ids = [room['id'] for room in rooms_data]
    if room_ids:
        connection.execute(
            room_table.delete().where(room_table.c.id.in_(room_ids))
        )