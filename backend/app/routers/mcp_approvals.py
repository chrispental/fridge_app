"""First-party human approval endpoints, deliberately absent from MCP tools.

CurrentUser accepts the application's browser session, not MCP OAuth tokens. All
writes use action-specific POST routes; reading a link never grants consent.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..database import get_db
from ..services import mcp_tools

router = APIRouter(prefix="/api/mcp-approvals", tags=["mcp-approvals"])


@router.get("/{approval_id}")
def get_approval(approval_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    return mcp_tools.get_shopping_approval(db, user.id, approval_id)


@router.post("/{approval_id}/approve")
def approve(approval_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    return mcp_tools.approve_shopping(db, user.id, approval_id)


@router.post("/{approval_id}/deny")
def deny(approval_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    return mcp_tools.deny_shopping(db, user.id, approval_id)
