"""Local mode refuses other web pages' requests (cross-site posts, DNS rebinding)."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import main as app_main
from app.browser_guard import LocalBrowserGuard
from app.config import settings

hits = []


def _client(base_url="http://localhost:8000"):
    app = FastAPI()
    app.add_middleware(LocalBrowserGuard)

    @app.get("/api/thing")
    def read():
        return {"ok": True}

    @app.post("/api/thing")
    def write():
        hits.append(1)
        return {"ok": True}

    return TestClient(app, base_url=base_url)


@pytest.fixture(autouse=True)
def local_mode(monkeypatch):
    hits.clear()
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "cors_origins", "http://localhost:5173,http://localhost:8080")
    monkeypatch.setattr(settings, "local_allowed_hosts", "localhost,127.0.0.1,::1")


@pytest.mark.parametrize("origin", ["https://evil.example", "http://localhost.evil.example", "null"])
def test_cross_site_writes_are_refused_before_the_handler(origin):
    # What a form post or no-cors fetch from another page looks like: no preflight.
    r = _client().post("/api/thing", headers={"Origin": origin, "Content-Type": "text/plain"})
    assert r.status_code == 403 and hits == []


@pytest.mark.parametrize("origin", ["http://localhost:8080", "http://127.0.0.1:8080", "http://[::1]:8080", "http://localhost:5173"])
def test_the_app_itself_can_write(origin):
    assert _client().post("/api/thing", headers={"Origin": origin}).status_code == 200


def test_scripts_without_an_origin_still_work():
    assert _client().post("/api/thing").status_code == 200 and hits == [1]


@pytest.mark.parametrize("base_url", ["http://rebind.evil.example:8000", "http://evil.example"])
def test_unknown_hosts_are_refused_so_rebinding_cannot_read(base_url):
    assert _client(base_url).get("/api/thing").status_code == 403


@pytest.mark.parametrize("base_url", ["http://localhost:8000", "http://127.0.0.1:8080", "http://[::1]:8000", "http://LOCALHOST"])
def test_local_hosts_are_served(base_url):
    assert _client(base_url).get("/api/thing").status_code == 200


def test_extra_hosts_can_be_allowed(monkeypatch):
    monkeypatch.setattr(settings, "local_allowed_hosts", "localhost,fridge.lan")
    assert _client("http://fridge.lan:8080").get("/api/thing").status_code == 200
    monkeypatch.setattr(settings, "local_allowed_hosts", "*")
    assert _client("http://anything.example").get("/api/thing").status_code == 200


def test_cloud_mode_is_untouched(monkeypatch):
    # Bearer tokens aren't attached by the browser on its own; the auth seam handles it.
    monkeypatch.setattr(settings, "supabase_url", "https://abc123.supabase.co")
    client = _client("https://fridge.example.com")
    assert client.post("/api/thing", headers={"Origin": "https://elsewhere.example"}).status_code == 200


def test_the_app_installs_the_guard():
    assert any(m.cls is LocalBrowserGuard for m in app_main.app.user_middleware)
