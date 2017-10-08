"""
add user_id to access_token table

Revision ID: f5ed741311b9
Revises: f013a6b67f91
Create Date: 2017-10-06 16:40:43.472109

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f5ed741311b9'
down_revision = 'f013a6b67f91'


def upgrade():
    op.add_column('oauth2_access_token',
        sa.Column('user_id', sa.UnicodeText),
    )



def downgrade():
    pass
