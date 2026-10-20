"""First-party human approval endpoints, deliberately absent from MCP tools.

CurrentUser accepts the application's browser session, not MCP OAuth tokens. All
writes use action-specific POST routes; reading a link never grants consent.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..config import LOCAL_MCP_HOST, LOCAL_MCP_ORIGIN, settings
from ..database import get_db
from ..services import mcp_tools

def local_approval_guard(request: Request) -> None:
    """Browser accident guard, not protection from trusted same-host programs."""
    if settings.mcp_mode != "local":
        return
    headers = request.headers
    if headers.getlist("host") != [LOCAL_MCP_HOST]:
        raise HTTPException(421, "Open the approval in the local Fridge Chef UI")
    if "authorization" in headers:
        raise HTTPException(403, "Local approvals do not accept Authorization")
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if headers.getlist("origin") != [LOCAL_MCP_ORIGIN]:
            raise HTTPException(403, "Approve or deny from the local Fridge Chef UI")
        if headers.getlist("x-fridge-mcp-approval") != ["1"]:
            raise HTTPException(403, "Local approval confirmation header required")
        content_types = headers.getlist("content-type")
        if (len(content_types) != 1
                or content_types[0].split(";", 1)[0].strip().lower() != "application/json"):
            raise HTTPException(415, "Local approval requires application/json")


router = APIRouter(prefix="/api/mcp-approvals", tags=["mcp-approvals"],
                   dependencies=[Depends(local_approval_guard)])


@router.get("/{approval_id}")
def get_approval(approval_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    return mcp_tools.get_shopping_approval(db, user.id, approval_id)


@router.post("/{approval_id}/approve")
def approve(approval_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    return mcp_tools.approve_shopping(db, user.id, approval_id)


@router.post("/{approval_id}/deny")
def deny(approval_id: str, user: CurrentUser, db: Session = Depends(get_db)):
    return mcp_tools.deny_shopping(db, user.id, approval_id)
