"""Add profile_image_url to users table

Revision ID: add_profile_image_url
Revises: cac5ce25728d
Create Date: 2024-01-15 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_profile_image_url'
down_revision = 'cac5ce25728d'
branch_labels = None
depends_on = None


def upgrade():
    # Add profile_image_url column to users table
    op.add_column('users', sa.Column('profile_image_url', sa.String(length=500), nullable=True))


def downgrade():
    # Remove profile_image_url column from users table
    op.drop_column('users', 'profile_image_url')

