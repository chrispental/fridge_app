"""Explicit local HTTP profile regressions; synthetic data and no sockets.

The Docker profile provides the loopback network boundary. These tests exercise
the exact-host/browser guards and the same approval services as remote MCP.
"""
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp_types.version import LATEST_HANDSHAKE_VERSION
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import mcp_auth, mcp_server, models
from app.auth import get_current_user
from app.config import (
    DEFAULT_LOCAL_USER_ID, LOCAL_MCP_API_HOST, LOCAL_MCP_HOST, LOCAL_MCP_ORIGIN,
    LOCAL_MCP_RESOURCE_URL, Settings, settings,
)
from app.database import Base, get_db
from app.models import utcnow
from app.routers import inventory, mcp_approvals
from app.services import mcp_tools

OTHER_USER = "11111111-1111-4111-8111-111111111111"
APPROVAL_HEADERS = {
    "Origin": LOCAL_MCP_ORIGIN,
    "X-Fridge-MCP-Approval": "1",
    "Content-Type": "application/json",
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def local_config(monkeypatch):
    for key, value in {
        "mcp_enabled": True, "mcp_mode": "local", "supabase_url": "",
        "mcp_resource_url": LOCAL_MCP_RESOURCE_URL,
        "mcp_issuer_url": "", "mcp_jwks_url": "", "mcp_grants": [],
        "local_user_id": DEFAULT_LOCAL_USER_ID,
    }.items():
        monkeypatch.setattr(settings, key, value)


@pytest.fixture
def local_setup(local_config, monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add(models.User(id=OTHER_USER))
        db.flush()
        db.add(models.InventoryItem(user_id=OTHER_USER, name="other user's private apples"))
        db.commit()
    monkeypatch.setattr(mcp_server, "SessionLocal", sessions)

    def isolated_db():
        with sessions() as db:
            yield db

    server, transport = mcp_server.build_mcp_app()
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware, allow_origins=[LOCAL_MCP_ORIGIN],
        allow_methods=["*"], allow_headers=["*"],
    )
    app.add_middleware(mcp_server.LocalMcpAppGuard)
    app.dependency_overrides[get_db] = isolated_db
    app.include_router(inventory.router)
    app.include_router(mcp_approvals.router)
    app.mount("/", transport)
    yield SimpleNamespace(server=server, transport=transport, app=app, sessions=sessions)
    engine.dispose()


@pytest.fixture
async def local_client(local_setup):
    async with local_setup.transport.lifespan(local_setup.transport):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=local_setup.app),
            base_url=LOCAL_MCP_ORIGIN,
            headers={
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": LATEST_HANDSHAKE_VERSION,
            },
        ) as client:
            yield client


async def rpc(client, method, params=None, **kwargs):
    return await client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": method, "params": params or {},
    }, **kwargs)


async def call_tool(client, name, arguments=None, **kwargs):
    return await rpc(client, "tools/call", {"name": name, "arguments": arguments or {}}, **kwargs)


def result(response):
    assert response.status_code == 200, response.text
    body = response.json()
    assert "error" not in body, body
    assert not body["result"].get("isError", False), body
    return body["result"]


def tool_error(response, message):
    assert response.status_code == 200, response.text
    body = response.json()
    assert "error" not in body, body
    assert body["result"]["isError"] is True, body
    assert message in " ".join(item.get("text", "") for item in body["result"]["content"])


def make_plan(sessions):
    with sessions() as db:
        user = get_current_user(creds=None, db=db)
        meal = models.Meal(
            user_id=user.id, title="Rice dinner", title_normalized="rice dinner",
            status="suggested", recipe_json={"ingredients": [
                {"name": "rice", "quantity": 4, "unit": "cup"},
            ]},
        )
        plan = models.MealPlan(user_id=user.id, status="ready")
        plan.entries = [models.MealPlanEntry(slot_index=0, meal=meal)]
        db.add(plan)
        db.commit()
        return plan.id


async def preview(client, sessions):
    plan_id = make_plan(sessions)
    return result(await call_tool(client, "preview_plan_shopping", {"plan_id": plan_id}))["structuredContent"]


def test_disabled_and_remote_are_the_defaults():
    assert Settings.model_fields["mcp_enabled"].default is False
    assert Settings.model_fields["mcp_mode"].default == "remote"


def test_explicit_local_configuration(local_config):
    mcp_auth.validate_configuration()


@pytest.mark.parametrize("field,value", [
    ("mcp_enabled", False),
    ("mcp_mode", "invalid"),
    ("mcp_mode", "remote"),
    ("supabase_url", "https://cloud.supabase.co"),
    ("mcp_resource_url", ""),
    ("mcp_resource_url", "http://localhost:18080/mcp"),
    ("mcp_resource_url", "http://127.0.0.1:18000/mcp"),
    ("mcp_resource_url", "http://127.0.0.1:8080/mcp"),
    ("mcp_resource_url", "http://0.0.0.0:18080/mcp"),
    ("mcp_resource_url", "http://192.168.1.2:18080/mcp"),
    ("mcp_resource_url", "http://fridge.example:18080/mcp"),
    ("mcp_resource_url", "https://127.0.0.1:18080/mcp"),
    ("mcp_resource_url", LOCAL_MCP_RESOURCE_URL + "/"),
    ("mcp_resource_url", LOCAL_MCP_RESOURCE_URL + "?local=true"),
    ("mcp_resource_url", LOCAL_MCP_RESOURCE_URL + "#local"),
    ("mcp_resource_url", "http://user@127.0.0.1:18080/mcp"),
    ("mcp_issuer_url", "https://identity.example/"),
    ("mcp_jwks_url", "https://identity.example/jwks.json"),
    ("mcp_grants", [{"subject": "unexpected"}]),
    ("local_user_id", "not-a-uuid"),
])
def test_unsafe_local_configuration_fails_closed(local_config, monkeypatch, field, value):
    monkeypatch.setattr(settings, field, value)
    with pytest.raises(ValueError):
        mcp_server.build_mcp_app()


@pytest.mark.anyio
async def test_local_http_initializes_without_oauth_and_lists_only_five_tools(local_client, local_setup):
    assert local_setup.server.auth is None
    initialized = result(await rpc(local_client, "initialize", {
        "protocolVersion": LATEST_HANDSHAKE_VERSION,
        "capabilities": {}, "clientInfo": {"name": "local-test", "version": "1"},
    }))
    assert initialized["serverInfo"]["name"] == "Fridge Chef"
    assert "tasks" not in initialized["capabilities"]
    tools = result(await rpc(local_client, "tools/list"))["tools"]
    assert {tool["name"] for tool in tools} == {
        "read_inventory", "search_recipes", "get_current_plan",
        "preview_plan_shopping", "import_plan_shopping",
    }
    for tool in tools:
        assert not {"user_id", "client_id"} & tool["inputSchema"].get("properties", {}).keys()
    for path in (
        "/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/mcp",
        "/.well-known/oauth-authorization-server", "/authorize", "/token", "/sse",
    ):
        response = await local_client.get(path)
        assert response.status_code == 404, (path, response.text)
        assert "www-authenticate" not in response.headers


@pytest.mark.anyio
async def test_first_local_tool_uses_normal_app_user_creation(local_client, local_setup):
    with local_setup.sessions() as db:
        assert db.get(models.User, DEFAULT_LOCAL_USER_ID) is None
    found = result(await call_tool(local_client, "read_inventory"))["structuredContent"]
    assert found["items"] == []
    with local_setup.sessions() as db:
        assert db.get(models.User, DEFAULT_LOCAL_USER_ID) is not None
        assert db.query(models.User).count() == 2


@pytest.mark.anyio
async def test_first_preview_ensures_local_user_before_domain_write(local_client, local_setup, monkeypatch):
    def check(db, user_id, *, client_id, **kwargs):
        assert user_id == DEFAULT_LOCAL_USER_ID
        assert db.get(models.User, user_id) is not None
        assert client_id == mcp_auth.LOCAL_CLIENT_ID
        return {"checked": True}

    monkeypatch.setattr(mcp_tools, "preview_plan_shopping", check)
    assert result(await call_tool(local_client, "preview_plan_shopping"))["structuredContent"] == {"checked": True}


@pytest.mark.anyio
@pytest.mark.parametrize("headers,status", [
    ({"Origin": LOCAL_MCP_ORIGIN}, 403),
    ({"Origin": "http://attacker.example"}, 403),
    ({"Origin": "null"}, 403),
    ({"Origin": ""}, 403),
    ({"Authorization": "Bearer any-token"}, 403),
    ({"Authorization": ""}, 403),
    ({"Host": "localhost:18080"}, 421),
    ({"Host": "127.0.0.1"}, 421),
    ({"Host": LOCAL_MCP_API_HOST}, 421),
    ({"Host": "attacker.example", "X-Forwarded-Host": LOCAL_MCP_HOST,
      "X-Forwarded-For": "127.0.0.1"}, 421),
])
async def test_local_mcp_rejects_browser_auth_and_host_ambiguity(local_client, headers, status):
    assert (await rpc(local_client, "tools/list", headers=headers)).status_code == status


@pytest.mark.anyio
async def test_cors_preflight_cannot_bypass_mcp_browser_guard(local_client):
    for path in ("/mcp", "/mcp/"):
        response = await local_client.options(path, headers={
            "Origin": LOCAL_MCP_ORIGIN, "Access-Control-Request-Method": "POST",
        })
        assert response.status_code == 403


@pytest.mark.anyio
@pytest.mark.parametrize("headers,status", [
    ({"Host": "attacker.example"}, 421),
    ({"Host": "localhost:18080"}, 421),
    ({"Origin": "http://attacker.example"}, 403),
    ({"Origin": "null"}, 403),
    ({"Host": "attacker.example", "X-Forwarded-Host": LOCAL_MCP_HOST}, 421),
])
async def test_local_profile_guards_ordinary_rest_api_too(local_client, headers, status):
    assert (await local_client.get("/api/inventory", headers=headers)).status_code == status


@pytest.mark.anyio
@pytest.mark.parametrize("host", [LOCAL_MCP_HOST, LOCAL_MCP_API_HOST])
async def test_local_rest_accepts_exact_ui_and_api_hosts(local_client, host):
    response = await local_client.get("/api/inventory", headers={"Host": host})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.anyio
async def test_real_local_preview_human_approval_import_and_replay(local_client, local_setup):
    prepared = await preview(local_client, local_setup.sessions)
    key = prepared["approval_id"]
    assert prepared["approval_url"] == f"{LOCAL_MCP_ORIGIN}/mcp-approvals/{key}"
    assert prepared["client_id"] == mcp_auth.LOCAL_CLIENT_ID
    assert prepared["status"] == "pending"
    # Reading never approves, and MCP exposes no approval tool.
    read = await local_client.get(f"/api/mcp-approvals/{key}")
    assert read.status_code == 200 and read.json()["status"] == "pending"
    tool_error(await call_tool(local_client, "import_plan_shopping", {"approval_id": key}), "explicitly approve")
    approved = await local_client.post(f"/api/mcp-approvals/{key}/approve", headers=APPROVAL_HEADERS, json={})
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    with local_setup.sessions() as db:
        assert db.query(models.ShoppingListItem).count() == 0
    imported = result(await call_tool(local_client, "import_plan_shopping", {"approval_id": key}))["structuredContent"]
    assert imported["status"] == "imported"
    # A consumed approval remains a stable replay even after its expiry.
    with local_setup.sessions() as db:
        db.get(models.MCPShoppingApproval, key).expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    replay = result(await call_tool(local_client, "import_plan_shopping", {"approval_id": key}))["structuredContent"]
    assert replay == imported
    with local_setup.sessions() as db:
        rows = db.query(models.ShoppingListItem).all()
        assert len(rows) == 1 and rows[0].quantity == 4
        assert rows[0].user_id == DEFAULT_LOCAL_USER_ID


@pytest.mark.anyio
@pytest.mark.parametrize("action", ["approve", "deny"])
@pytest.mark.parametrize("overrides,status", [
    ({"Origin": None}, 403),
    ({"Origin": "null"}, 403),
    ({"Origin": "http://attacker.example"}, 403),
    ({"Origin": "http://localhost:18080"}, 403),
    ({"X-Fridge-MCP-Approval": None}, 403),
    ({"X-Fridge-MCP-Approval": "0"}, 403),
    ({"Content-Type": None}, 415),
    ({"Content-Type": "text/plain"}, 415),
    ({"Content-Type": "application/x-www-form-urlencoded"}, 415),
    ({"Authorization": "Bearer any-token"}, 403),
    ({"Host": LOCAL_MCP_API_HOST}, 421),
])
async def test_local_approval_writes_need_first_party_origin_and_headers(
    local_client, local_setup, action, overrides, status,
):
    key = (await preview(local_client, local_setup.sessions))["approval_id"]
    headers = {key: value for key, value in {**APPROVAL_HEADERS, **overrides}.items() if value is not None}
    response = await local_client.post(f"/api/mcp-approvals/{key}/{action}", headers=headers, content=b"{}")
    assert response.status_code == status, response.text
    with local_setup.sessions() as db:
        assert db.get(models.MCPShoppingApproval, key).status == "pending"
        assert db.query(models.ShoppingListItem).count() == 0


@pytest.mark.anyio
async def test_local_human_can_deny_and_import_stays_blocked(local_client, local_setup):
    key = (await preview(local_client, local_setup.sessions))["approval_id"]
    denied = await local_client.post(f"/api/mcp-approvals/{key}/deny", headers=APPROVAL_HEADERS, json={})
    assert denied.status_code == 200 and denied.json()["status"] == "rejected"
    tool_error(await call_tool(local_client, "import_plan_shopping", {"approval_id": key}), "no longer available")


@pytest.mark.anyio
@pytest.mark.parametrize("approved", [False, True])
@pytest.mark.parametrize("change", ["expired", "stale"])
async def test_local_expiry_and_staleness_preserve_the_shopping_list(local_client, local_setup, approved, change):
    key = (await preview(local_client, local_setup.sessions))["approval_id"]
    if approved:
        response = await local_client.post(f"/api/mcp-approvals/{key}/approve", headers=APPROVAL_HEADERS, json={})
        assert response.status_code == 200
    with local_setup.sessions() as db:
        if change == "expired":
            db.get(models.MCPShoppingApproval, key).expires_at = utcnow() - timedelta(seconds=1)
        else:
            db.add(models.InventoryItem(user_id=DEFAULT_LOCAL_USER_ID, name="rice", quantity=1, unit="cup"))
        db.commit()
    if not approved:
        response = await local_client.post(f"/api/mcp-approvals/{key}/approve", headers=APPROVAL_HEADERS, json={})
        assert response.status_code == (410 if change == "expired" else 409)
    tool_error(await call_tool(local_client, "import_plan_shopping", {"approval_id": key}),
               "expired" if change == "expired" else ("changed" if approved else "no longer available"))
    with local_setup.sessions() as db:
        assert db.query(models.ShoppingListItem).count() == 0


@pytest.mark.anyio
async def test_local_identity_cannot_be_chosen_by_tool_arguments(local_client):
    response = await call_tool(local_client, "read_inventory", {"user_id": OTHER_USER, "client_id": "attacker"})
    assert response.status_code == 200
    assert "other user's private apples" not in response.text


@pytest.mark.anyio
async def test_local_body_limit_still_applies_before_tool_dispatch(local_client):
    response = await local_client.post("/mcp", content=b"x" * (16 * 1024 + 1),
                                       headers={"Content-Type": "application/json"})
    assert response.status_code == 413
