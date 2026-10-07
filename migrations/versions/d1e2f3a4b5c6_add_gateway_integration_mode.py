"""Add integration_mode to gateways.

Revision ID: d1e2f3a4b5c6
Revises: a9b1c2d3e4f7
Create Date: 2026-03-04 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "d1e2f3a4b5c6"
down_revision = "a9b1c2d3e4f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add gateway integration_mode column.

    Supported values:
      - "openclaw_v3" (default): canonical OpenClaw gateway WebSocket JSON-RPC v3.
      - "rest_bridge": HTTP/JSON bridge served by per-tenant tenant-platform
        Cloud Run services at POST /api/v1/rpc/:method (and GET /healthz).
    """
    op.add_column(
        "gateways",
        sa.Column(
            "integration_mode",
            sa.String(length=32),
            nullable=False,
            server_default="openclaw_v3",
        ),
    )
    op.alter_column("gateways", "integration_mode", server_default=None)


def downgrade() -> None:
    """Remove gateway integration_mode column."""
    op.drop_column("gateways", "integration_mode")
