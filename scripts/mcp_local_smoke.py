"""Real nginx/backend + Chromium local approval smoke test; synthetic CI only."""
import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from playwright.sync_api import sync_playwright, expect

ORIGIN = "http://127.0.0.1:18080"


def request(path, data=None, headers=None):
    req = Request(ORIGIN + path, data=data, headers=headers or {})
    try:
        with urlopen(req, timeout=15) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


def rpc(method, params=None):
    # Respect the edge rate limit, including on fast runners.
    time.sleep(0.15)
    status, body = request("/mcp", json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": method, "params": params or {},
    }).encode(), {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
    assert status == 200, (status, body)
    parsed = json.loads(body)
    assert "error" not in parsed, parsed
    return parsed["result"]


def tool(name, arguments=None, *, error=False):
    result = rpc("tools/call", {"name": name, "arguments": arguments or {}})
    assert bool(result.get("isError")) == error, result
    return result if error else result["structuredContent"]


rpc("initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                   "clientInfo": {"name": "synthetic-ci", "version": "1"}})
assert {t["name"] for t in rpc("tools/list")["tools"]} == {
    "read_inventory", "search_recipes", "get_current_plan",
    "preview_plan_shopping", "import_plan_shopping",
}
assert tool("read_inventory")["items"] == []
assert tool("search_recipes", {"favorites_only": True})["recipes"]
assert tool("get_current_plan")
preview = tool("preview_plan_shopping")
approval_id = preview["approval_id"]
assert preview["approval_url"] == f"{ORIGIN}/mcp-approvals/{approval_id}"
tool("import_plan_shopping", {"approval_id": approval_id}, error=True)
assert request("/.well-known/oauth-protected-resource/mcp")[0] == 404
assert request("/api/health", headers={"Host": "evil.example"})[0] == 421
assert request("/mcp", b"{}", {"Origin": ORIGIN, "Content-Type": "application/json"})[0] == 403
decision_path = f"/api/mcp-approvals/{approval_id}/approve"
assert request(decision_path, b"{}", {"Content-Type": "application/json"})[0] == 403
assert request(decision_path, b"{}", {"Content-Type": "application/json", "Origin": ORIGIN})[0] == 403

with sync_playwright() as p:
    browser = p.chromium.launch()
    for theme in ("light", "dark"):
        for label, viewport in (("desktop", {"width": 1280, "height": 900}),
                                ("phone", {"width": 390, "height": 844})):
            context = browser.new_context(viewport=viewport, color_scheme=theme)
            context.add_init_script(f"localStorage.setItem('fridge-chef-theme', '{theme}')")
            page = context.new_page()
            failures = []
            page.on("pageerror", lambda error: failures.append(str(error)))
            page.goto(preview["approval_url"])
            expect(page.get_by_role("heading", name="Review shopping changes")).to_be_visible()
            expect(page.get_by_role("button", name="Approve these changes")).to_be_enabled()
            assert page.locator("html").get_attribute("data-theme") == theme
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Horizontal overflow"
            page.screenshot(path=f"/artifacts/local-approval-{label}-{theme}.png", full_page=True)
            assert not failures, failures
            context.close()
    # Reading/reloading/rendering never approves. Real browser click supplies
    # Origin and the application custom header through the production fetch code.
    assert json.loads(request(f"/api/mcp-approvals/{approval_id}")[1])["status"] == "pending"
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    page.goto(preview["approval_url"])
    page.get_by_role("button", name="Approve these changes").click()
    expect(page.get_by_role("button", name="Revoke approval")).to_be_visible()
    imported = tool("import_plan_shopping", {"approval_id": approval_id})
    assert tool("import_plan_shopping", {"approval_id": approval_id}) == imported
    page.get_by_role("button", name="Reload approval").click()
    expect(page.get_by_role("status").filter(has_text="applied to your shopping list")).to_be_visible()
    assert page.get_by_role("button", name="Approve these changes").count() == 0
    page.screenshot(path="/artifacts/local-approval-imported.png", full_page=True)
    browser.close()
print("Local MCP real HTTP + browser approval/replay smoke passed; four viewport/theme checks passed")
