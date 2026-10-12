"""Real SDK HTTP transport and tool-dispatch tests, without listening sockets.

The app's ASGI endpoint and lifespan run in process; JWTs use a synthetic JWKS key
and every database row lives in this test's disposable in-memory SQLite database.
"""
import json
import time
from types import SimpleNamespace

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types.version import LATEST_HANDSHAKE_VERSION
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import mcp_auth, mcp_server, models
from app.config import settings
from app.database import Base
from app.services import mcp_tools

ORIGIN = "https://fridge.example"
RESOURCE = ORIGIN + "/mcp"
ISSUER = "https://identity.example/"
CLIENT = "approved-chat-client"
ALICE = "11111111-1111-4111-8111-111111111111"
BOB = "22222222-2222-4222-8222-222222222222"
APPROVAL_ID = "33333333-3333-4333-8333-333333333333"
TOOL_NAMES = {
    "read_inventory", "search_recipes", "get_current_plan",
    "preview_plan_shopping", "import_plan_shopping",
}


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def http_setup(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "https://project.supabase.co")
    monkeypatch.setattr(settings, "mcp_enabled", True)
    monkeypatch.setattr(settings, "mcp_resource_url", RESOURCE)
    monkeypatch.setattr(settings, "mcp_issuer_url", ISSUER)
    monkeypatch.setattr(settings, "mcp_jwks_url", "https://identity.example/jwks.json")
    monkeypatch.setattr(settings, "mcp_grants", [{
        "subject": subject, "client_id": CLIENT, "user_id": user_id,
        "scopes": ["fridge:read", "fridge:shopping"],
    } for subject, user_id in [("alice", ALICE), ("bob", BOB)]])
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add_all([models.User(id=ALICE), models.User(id=BOB)])
        db.flush()
        db.add_all([
            models.InventoryItem(user_id=ALICE, name="alice apples", storage="fridge"),
            models.InventoryItem(user_id=BOB, name="bob bananas", storage="pantry"),
        ])
        db.commit()
    monkeypatch.setattr(mcp_auth, "SessionLocal", sessions)
    monkeypatch.setattr(mcp_server, "SessionLocal", sessions)
    private = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(mcp_auth, "_jwk_client", lambda url: SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private.public_key()),
    ))

    def token(**overrides):
        now = int(time.time())
        return jwt.encode({
            "iss": ISSUER, "aud": RESOURCE, "sub": "alice", "client_id": CLIENT,
            "scope": "fridge:read fridge:shopping", "iat": now, "exp": now + 300,
            "jti": "synthetic-http-access-token-id",
            **overrides,
        }, private, algorithm="ES256", headers={"typ": "at+jwt", "kid": "test-key"})

    server, app = mcp_server.build_mcp_app()
    yield SimpleNamespace(server=server, app=app, sessions=sessions, token=token)
    engine.dispose()


@pytest.fixture
async def client(http_setup):
    async with http_setup.server.session_manager.run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=http_setup.app), base_url=ORIGIN,
            headers={
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": LATEST_HANDSHAKE_VERSION,
                "Authorization": f"Bearer {http_setup.token()}",
            },
        ) as test_client:
            yield test_client


async def rpc(client, method, params=None, **kwargs):
    return await client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": method, "params": params or {},
    }, **kwargs)


async def call_tool(client, name, arguments=None, **kwargs):
    return await rpc(client, "tools/call", {"name": name, "arguments": arguments or {}}, **kwargs)


def successful_result(response):
    assert response.status_code == 200, response.text
    body = response.json()
    assert "error" not in body, body
    result = body["result"]
    assert result.get("isError", False) is False, result
    return result


def tool_error(response, text=None):
    assert response.status_code == 200, response.text
    body = response.json()
    assert "error" not in body, body
    result = body["result"]
    assert result["isError"] is True, result
    if text is not None:
        assert text in " ".join(item.get("text", "") for item in result["content"])
    return result


@pytest.mark.anyio
async def test_initialize_list_and_call_use_real_http_transport(client):
    response = await rpc(client, "initialize", {
        "protocolVersion": LATEST_HANDSHAKE_VERSION,
        "capabilities": {}, "clientInfo": {"name": "synthetic-tests", "version": "1"},
    })
    result = successful_result(response)
    assert result["serverInfo"]["name"] == "Fridge Chef"
    assert "tools" in result["capabilities"]
    assert "mcp-session-id" not in response.headers

    tools = successful_result(await rpc(client, "tools/list"))["tools"]
    assert {tool["name"] for tool in tools} == TOOL_NAMES
    for tool in tools:
        assert "user_id" not in tool["inputSchema"].get("properties", {})
        assert "client_id" not in tool["inputSchema"].get("properties", {})
        assert tool["annotations"]["openWorldHint"] is False
        assert tool["annotations"]["destructiveHint"] is False
    by_name = {tool["name"]: tool for tool in tools}
    for name in ("read_inventory", "search_recipes", "get_current_plan"):
        assert by_name[name]["annotations"]["readOnlyHint"] is True
    assert by_name["preview_plan_shopping"]["annotations"]["readOnlyHint"] is False
    assert by_name["import_plan_shopping"]["annotations"]["idempotentHint"] is True

    inventory = successful_result(await call_tool(client, "read_inventory"))["structuredContent"]
    assert [item["name"] for item in inventory["items"]] == ["alice apples"]


@pytest.mark.anyio
async def test_protected_resource_metadata_and_bearer_challenge(client):
    response = await client.get("/.well-known/oauth-protected-resource/mcp", headers={"Authorization": ""})
    assert response.status_code == 200
    metadata = response.json()
    assert metadata["resource"] == RESOURCE
    assert metadata["authorization_servers"] == [ISSUER]
    assert set(metadata["scopes_supported"]) == {"fridge:read", "fridge:shopping"}
    assert metadata["bearer_methods_supported"] == ["header"]

    denied = await rpc(client, "tools/list", headers={"Authorization": ""})
    assert denied.status_code == 401
    challenge = denied.headers["www-authenticate"]
    assert challenge.startswith("Bearer ")
    assert f'resource_metadata="{ORIGIN}/.well-known/oauth-protected-resource/mcp"' in challenge


@pytest.mark.anyio
@pytest.mark.parametrize("authorization", ["", "Basic ignored", "Bearer invalid-token"])
async def test_missing_and_invalid_bearers_are_rejected(client, authorization):
    response = await call_tool(client, "read_inventory", headers={"Authorization": authorization})
    assert response.status_code == 401
    assert "alice apples" not in response.text


@pytest.mark.anyio
@pytest.mark.parametrize("claims", [
    {"aud": "authenticated"},
    {"aud": [RESOURCE]},
    {"iss": "https://project.supabase.co/auth/v1"},
    {"client_id": "unapproved-client"},
    {"sub": "unmapped-user"},
    {"scope": "fridge:shopping"},
    {"exp": 1},
])
async def test_real_signed_but_unauthorized_tokens_are_rejected(client, http_setup, claims):
    response = await call_tool(client, "read_inventory", headers={
        "Authorization": f"Bearer {http_setup.token(**claims)}",
    })
    assert response.status_code == 401


@pytest.mark.anyio
async def test_each_stateless_request_is_bound_to_its_own_user(client, http_setup):
    first = successful_result(await call_tool(client, "read_inventory"))["structuredContent"]
    second = successful_result(await call_tool(client, "read_inventory", headers={
        "Authorization": f"Bearer {http_setup.token(sub='bob')}",
    }))["structuredContent"]
    assert [item["name"] for item in first["items"]] == ["alice apples"]
    assert [item["name"] for item in second["items"]] == ["bob bananas"]
    denied = await call_tool(client, "read_inventory", headers={"Authorization": ""})
    assert denied.status_code == 401


@pytest.mark.anyio
async def test_real_preview_requires_human_approval_then_import_replays(client, http_setup):
    with http_setup.sessions() as db:
        meal = models.Meal(
            user_id=ALICE, title="Carrot soup", title_normalized="carrot soup",
            status="suggested", recipe_json={"ingredients": [
                {"name": "carrots", "quantity": 2, "unit": "cup"},
            ]},
        )
        plan = models.MealPlan(user_id=ALICE, status="ready")
        db.add_all([meal, plan])
        db.flush()
        db.add(models.MealPlanEntry(plan_id=plan.id, meal_id=meal.id, slot_index=0))
        db.commit()
        plan_id = plan.id

    preview = successful_result(await call_tool(
        client, "preview_plan_shopping", {"plan_id": plan_id},
    ))["structuredContent"]
    approval_id = preview["approval_id"]
    assert preview["status"] == "pending"
    assert preview["approval_url"] == f"{ORIGIN}/mcp-approvals/{approval_id}"
    assert preview["changes"]
    tool_error(await call_tool(client, "import_plan_shopping", {
        "approval_id": approval_id,
    }), "explicitly approve")
    with http_setup.sessions() as db:
        assert db.query(models.ShoppingListItem).count() == 0
        # Simulate the separate first-party approval action. There is no MCP
        # tool that can perform this step, and the list is still unchanged.
        mcp_tools.approve_shopping(db, ALICE, approval_id)
        assert db.query(models.ShoppingListItem).count() == 0

    imported = successful_result(await call_tool(client, "import_plan_shopping", {
        "approval_id": approval_id,
    }))["structuredContent"]
    replay = successful_result(await call_tool(client, "import_plan_shopping", {
        "approval_id": approval_id,
    }))["structuredContent"]
    assert imported["status"] == "imported"
    assert replay == imported
    with http_setup.sessions() as db:
        rows = db.query(models.ShoppingListItem).all()
        assert len(rows) == 1
        assert rows[0].user_id == ALICE
        assert rows[0].quantity == 2


@pytest.mark.anyio
async def test_identity_arguments_cannot_override_the_authenticated_user(client):
    # The SDK may reject unknown arguments or ignore them; neither may change
    # which user the operation receives.
    response = await call_tool(client, "read_inventory", {"user_id": BOB, "client_id": "attacker"})
    assert response.status_code == 200
    assert "bob bananas" not in response.text
    body = response.json()
    if "error" not in body and not body["result"].get("isError", False):
        assert [item["name"] for item in body["result"]["structuredContent"]["items"]] == ["alice apples"]


@pytest.mark.anyio
@pytest.mark.parametrize("tool,args", [
    ("preview_plan_shopping", {}),
    ("import_plan_shopping", {"approval_id": APPROVAL_ID}),
])
async def test_read_only_token_cannot_prepare_or_import_shopping(client, http_setup, monkeypatch, tool, args):
    def forbidden(*args, **kwargs):
        pytest.fail("A shopping operation ran without its required scope")

    monkeypatch.setattr(mcp_tools, "preview_plan_shopping", forbidden)
    monkeypatch.setattr(mcp_tools, "import_approved_plan_shopping", forbidden)
    tool_error(await call_tool(client, tool, args, headers={
        "Authorization": f"Bearer {http_setup.token(scope='fridge:read')}",
    }), "Insufficient scope")
    with http_setup.sessions() as db:
        assert db.query(models.ShoppingListItem).count() == 0


@pytest.mark.anyio
@pytest.mark.parametrize("name,args,operation", [
    ("read_inventory", {"query": "apple", "limit": 2, "offset": 1}, "inventory"),
    ("search_recipes", {"query": "soup", "favorites_only": True, "limit": 3, "offset": 2}, "search_recipes"),
    ("get_current_plan", {}, "current_plan"),
    ("preview_plan_shopping", {"plan_id": 7}, "preview_plan_shopping"),
    ("import_plan_shopping", {"approval_id": APPROVAL_ID}, "import_approved_plan_shopping"),
])
async def test_all_tools_pass_server_derived_identity(client, monkeypatch, name, args, operation):
    calls = []

    def record(db, user_id, **kwargs):
        calls.append((user_id, kwargs))
        return {"ok": True}

    monkeypatch.setattr(mcp_tools, operation, record)
    result = successful_result(await call_tool(client, name, args))
    assert result["structuredContent"] == {"ok": True}
    assert len(calls) == 1
    user_id, supplied = calls[0]
    assert user_id == ALICE
    assert all(supplied[key] == value for key, value in args.items())
    if name in {"preview_plan_shopping", "import_plan_shopping"}:
        assert supplied["client_id"] == CLIENT
    if name == "preview_plan_shopping":
        assert supplied["approval_base_url"] == ORIGIN


@pytest.mark.anyio
@pytest.mark.parametrize("name,args", [
    ("read_inventory", {"query": "x" * 101}),
    ("read_inventory", {"limit": 0}),
    ("read_inventory", {"limit": 101}),
    ("read_inventory", {"offset": -1}),
    ("read_inventory", {"offset": 10001}),
    ("search_recipes", {"limit": 51}),
    ("preview_plan_shopping", {"plan_id": 0}),
    ("import_plan_shopping", {"approval_id": "not-an-approval"}),
    ("import_plan_shopping", {}),
])
async def test_invalid_tool_arguments_do_not_reach_domain_operations(client, monkeypatch, name, args):
    def forbidden(*args, **kwargs):
        pytest.fail("An invalid argument reached a domain operation")

    for operation in ("inventory", "search_recipes", "preview_plan_shopping", "import_approved_plan_shopping"):
        monkeypatch.setattr(mcp_tools, operation, forbidden)
    tool_error(await call_tool(client, name, args))


@pytest.mark.anyio
async def test_tools_fail_closed_without_auth_context(http_setup, monkeypatch):
    monkeypatch.setattr(mcp_server, "get_access_token", lambda: None)
    for name, args in [
        ("read_inventory", {}), ("search_recipes", {}), ("get_current_plan", {}),
        ("preview_plan_shopping", {}), ("import_plan_shopping", {"approval_id": APPROVAL_ID}),
    ]:
        with pytest.raises(ToolError, match="Authentication required"):
            await http_setup.server.call_tool(name, args)


@pytest.mark.anyio
async def test_authenticated_context_with_wrong_app_user_fails_closed(client, monkeypatch):
    async def verify(self, token):
        return AccessToken(
            token=token, client_id=CLIENT, subject="alice", scopes=["fridge:read"],
            expires_at=int(time.time()) + 300, resource=RESOURCE,
            claims={"iss": ISSUER, "app_user_id": BOB},
        )

    monkeypatch.setattr(mcp_auth.FridgeTokenVerifier, "verify_token", verify)
    tool_error(await call_tool(client, "read_inventory"), "Authentication required")


@pytest.mark.anyio
async def test_sdk_rejects_mock_verifier_token_for_other_resource(client, monkeypatch):
    async def verify(self, token):
        return AccessToken(
            token=token, client_id=CLIENT, subject="alice", scopes=["fridge:read"],
            expires_at=int(time.time()) + 300, resource="https://another.example/mcp",
            claims={"iss": ISSUER, "app_user_id": ALICE},
        )

    monkeypatch.setattr(mcp_auth.FridgeTokenVerifier, "verify_token", verify)
    assert (await call_tool(client, "read_inventory")).status_code == 401


@pytest.mark.anyio
async def test_sdk_rejects_mock_verifier_token_without_read_scope(client, monkeypatch):
    async def verify(self, token):
        return AccessToken(
            token=token, client_id=CLIENT, subject="alice", scopes=["fridge:shopping"],
            expires_at=int(time.time()) + 300, resource=RESOURCE,
            claims={"iss": ISSUER, "app_user_id": ALICE},
        )

    monkeypatch.setattr(mcp_auth.FridgeTokenVerifier, "verify_token", verify)
    response = await call_tool(client, "read_inventory")
    assert response.status_code == 403
    assert 'error="insufficient_scope"' in response.headers["www-authenticate"]


@pytest.mark.anyio
@pytest.mark.parametrize("headers,status", [
    ({"Host": "attacker.example"}, 421),
    ({"Origin": "https://attacker.example"}, 403),
    ({"Origin": "null"}, 403),
    ({"Origin": "http://fridge.example"}, 403),
])
async def test_transport_rejects_untrusted_host_and_origin(client, headers, status):
    assert (await rpc(client, "tools/list", headers=headers)).status_code == status


@pytest.mark.anyio
async def test_transport_accepts_its_configured_origin(client):
    successful_result(await rpc(client, "tools/list", headers={"Origin": ORIGIN}))


@pytest.mark.anyio
async def test_request_body_size_limit_applies_with_and_without_content_length(client):
    oversized = b"x" * (16 * 1024 + 1)
    response = await client.post("/mcp", content=oversized, headers={"Content-Type": "application/json"})
    assert response.status_code == 413

    async def chunks():
        yield oversized[:8192]
        yield oversized[8192:]

    request = client.build_request(
        "POST", "/mcp", content=chunks(), headers={"Content-Type": "application/json"},
    )
    assert "content-length" not in request.headers
    assert (await client.send(request)).status_code == 413


@pytest.mark.anyio
async def test_oversized_tool_output_is_rejected(client, monkeypatch):
    monkeypatch.setattr(mcp_tools, "inventory", lambda *args, **kwargs: {"data": "x" * (128 * 1024)})
    tool_error(await call_tool(client, "read_inventory"), "Result is too large")


@pytest.mark.anyio
async def test_near_limit_unicode_and_escaped_output_is_preserved(client, monkeypatch):
    payload = {"data": "\\" * 10000 + "🍎" * 10000}
    compact_size = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode())
    assert 60000 < compact_size <= 64 * 1024
    monkeypatch.setattr(mcp_tools, "inventory", lambda *args, **kwargs: payload)
    response = await call_tool(client, "read_inventory")
    result = successful_result(response)
    assert result["structuredContent"] == payload
    text_content = [item["text"] for item in result["content"] if item["type"] == "text"]
    assert len(text_content) == 1
    assert json.loads(text_content[0]) == payload
    # The SDK includes text plus structured representations; their serialized
    # wire envelope is larger than the compact application result.
    assert compact_size < len(response.content) < 1024 * 1024


@pytest.mark.anyio
async def test_domain_errors_are_safe_and_unexpected_errors_are_redacted(client, monkeypatch):
    def missing(*args, **kwargs):
        raise HTTPException(404, "Plan not found")

    monkeypatch.setattr(mcp_tools, "current_plan", missing)
    tool_error(await call_tool(client, "get_current_plan"), "Plan not found")

    def crash(*args, **kwargs):
        raise RuntimeError("database-secret-and-private-kitchen-data")

    monkeypatch.setattr(mcp_tools, "current_plan", crash)
    response = await call_tool(client, "get_current_plan")
    tool_error(response, "The operation could not be completed")
    assert "database-secret" not in response.text


def test_rate_limit_is_per_principal_and_expires(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(mcp_server, "monotonic", lambda: now[0])
    limiter = mcp_server.ToolRateLimiter()
    for _ in range(60):
        limiter.check(("alice", CLIENT))
    with pytest.raises(ToolError, match="Rate limit"):
        limiter.check(("alice", CLIENT))
    limiter.check(("bob", CLIENT))
    now[0] += 61
    limiter.check(("alice", CLIENT))
