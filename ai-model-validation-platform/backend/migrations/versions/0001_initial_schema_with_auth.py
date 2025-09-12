"""Initial schema with authentication support

Revision ID: 0001
Revises: 
Create Date: 2025-08-27 22:57:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create initial schema with authentication support."""
    
    # Create auth_users table - CRITICAL FOR DEPLOYMENT
    op.create_table('auth_users',
        sa.Column('id', sa.String(36), nullable=False, default=lambda: str(uuid.uuid4())),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('is_superuser', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_verified', sa.Boolean(), nullable=True, default=False),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create auth user indexes
    op.create_index('idx_auth_user_email_active', 'auth_users', ['email', 'is_active'])
    op.create_index('idx_auth_user_username_active', 'auth_users', ['username', 'is_active'])
    op.create_index('idx_auth_user_active_verified', 'auth_users', ['is_active', 'is_verified'])
    op.create_index('idx_auth_user_superuser_active', 'auth_users', ['is_superuser', 'is_active'])
    op.create_index('idx_auth_user_created_active', 'auth_users', ['created_at', 'is_active'])
    op.create_index('idx_auth_user_last_login', 'auth_users', ['last_login'])
    op.create_index(op.f('ix_auth_users_created_at'), 'auth_users', ['created_at'])
    op.create_index(op.f('ix_auth_users_email'), 'auth_users', ['email'])
    op.create_index(op.f('ix_auth_users_is_active'), 'auth_users', ['is_active'])
    op.create_index(op.f('ix_auth_users_is_superuser'), 'auth_users', ['is_superuser'])
    op.create_index(op.f('ix_auth_users_is_verified'), 'auth_users', ['is_verified'])
    op.create_index(op.f('ix_auth_users_username'), 'auth_users', ['username'])
    
    # Create unique constraints
    op.create_unique_constraint(None, 'auth_users', ['email'])
    op.create_unique_constraint(None, 'auth_users', ['username'])
    
    # Create user_sessions table
    op.create_table('user_sessions',
        sa.Column('id', sa.String(36), nullable=False, default=lambda: str(uuid.uuid4())),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('session_token', sa.String(), nullable=False),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_activity', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['auth_users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create user session indexes
    op.create_index('idx_session_user_active', 'user_sessions', ['user_id', 'is_active'])
    op.create_index('idx_session_token_active', 'user_sessions', ['session_token', 'is_active'])
    op.create_index('idx_session_expires_active', 'user_sessions', ['expires_at', 'is_active'])
    op.create_index('idx_session_user_activity', 'user_sessions', ['user_id', 'last_activity'])
    op.create_index('idx_session_ip_activity', 'user_sessions', ['ip_address', 'last_activity'])
    op.create_index('idx_session_cleanup', 'user_sessions', ['expires_at', 'is_active'])
    op.create_index(op.f('ix_user_sessions_created_at'), 'user_sessions', ['created_at'])
    op.create_index(op.f('ix_user_sessions_expires_at'), 'user_sessions', ['expires_at'])
    op.create_index(op.f('ix_user_sessions_ip_address'), 'user_sessions', ['ip_address'])
    op.create_index(op.f('ix_user_sessions_is_active'), 'user_sessions', ['is_active'])
    op.create_index(op.f('ix_user_sessions_last_activity'), 'user_sessions', ['last_activity'])
    op.create_index(op.f('ix_user_sessions_session_token'), 'user_sessions', ['session_token'])
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'])
    
    # Create unique constraint for session token
    op.create_unique_constraint(None, 'user_sessions', ['session_token'])
    
    # Create projects table
    op.create_table('projects',
        sa.Column('id', sa.String(36), nullable=False, default=lambda: str(uuid.uuid4())),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('camera_model', sa.String(), nullable=False),
        sa.Column('camera_view', sa.String(), nullable=False),
        sa.Column('lens_type', sa.String(), nullable=True),
        sa.Column('resolution', sa.String(), nullable=True),
        sa.Column('frame_rate', sa.Integer(), nullable=True),
        sa.Column('signal_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=True, default='Active'),
        sa.Column('owner_id', sa.String(36), nullable=True, default='anonymous'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create project indexes
    op.create_index(op.f('ix_projects_created_at'), 'projects', ['created_at'])
    op.create_index(op.f('ix_projects_name'), 'projects', ['name'])
    op.create_index(op.f('ix_projects_owner_id'), 'projects', ['owner_id'])
    op.create_index(op.f('ix_projects_status'), 'projects', ['status'])


def downgrade() -> None:
    """Remove initial schema."""
    
    # Drop projects table
    op.drop_index(op.f('ix_projects_status'), table_name='projects')
    op.drop_index(op.f('ix_projects_owner_id'), table_name='projects')
    op.drop_index(op.f('ix_projects_name'), table_name='projects')
    op.drop_index(op.f('ix_projects_created_at'), table_name='projects')
    op.drop_table('projects')
    
    # Drop user_sessions table
    op.drop_constraint(None, 'user_sessions', type_='unique')
    op.drop_index(op.f('ix_user_sessions_user_id'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_session_token'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_last_activity'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_is_active'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_ip_address'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_expires_at'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_created_at'), table_name='user_sessions')
    op.drop_index('idx_session_cleanup', table_name='user_sessions')
    op.drop_index('idx_session_ip_activity', table_name='user_sessions')
    op.drop_index('idx_session_user_activity', table_name='user_sessions')
    op.drop_index('idx_session_expires_active', table_name='user_sessions')
    op.drop_index('idx_session_token_active', table_name='user_sessions')
    op.drop_index('idx_session_user_active', table_name='user_sessions')
    op.drop_table('user_sessions')
    
    # Drop auth_users table
    op.drop_constraint(None, 'auth_users', type_='unique')
    op.drop_constraint(None, 'auth_users', type_='unique')
    op.drop_index(op.f('ix_auth_users_username'), table_name='auth_users')
    op.drop_index(op.f('ix_auth_users_is_verified'), table_name='auth_users')
    op.drop_index(op.f('ix_auth_users_is_superuser'), table_name='auth_users')
    op.drop_index(op.f('ix_auth_users_is_active'), table_name='auth_users')
    op.drop_index(op.f('ix_auth_users_email'), table_name='auth_users')
    op.drop_index(op.f('ix_auth_users_created_at'), table_name='auth_users')
    op.drop_index('idx_auth_user_last_login', table_name='auth_users')
    op.drop_index('idx_auth_user_created_active', table_name='auth_users')
    op.drop_index('idx_auth_user_superuser_active', table_name='auth_users')
    op.drop_index('idx_auth_user_active_verified', table_name='auth_users')
    op.drop_index('idx_auth_user_username_active', table_name='auth_users')
    op.drop_index('idx_auth_user_email_active', table_name='auth_users')
    op.drop_table('auth_users')