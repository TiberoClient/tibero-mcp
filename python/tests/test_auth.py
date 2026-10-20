from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from src.mcp.auth import ApiKeyMiddleware

KEY = "k" * 64


def _client() -> TestClient:
    async def echo(request):
        return PlainTextResponse(request.url.path)

    inner = Starlette(routes=[Route("/mcp", echo, methods=["POST"]), Route("/healthz", echo)])
    return TestClient(ApiKeyMiddleware(inner, [KEY, "second-key"]))


def test_rejects_missing_and_wrong_keys():
    client = _client()
    assert client.post("/mcp").status_code == 401
    assert client.post("/mcp", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.post("/wrong/mcp").status_code == 401


def test_accepts_bearer_and_x_api_key():
    client = _client()
    assert client.post("/mcp", headers={"Authorization": f"Bearer {KEY}"}).status_code == 200
    assert client.post("/mcp", headers={"authorization": "bearer second-key"}).status_code == 200
    assert client.post("/mcp", headers={"X-API-Key": KEY}).status_code == 200


def test_path_key_is_stripped_before_routing():
    response = _client().post(f"/{KEY}/mcp")
    assert response.status_code == 200
    assert response.text == "/mcp"


def test_health_is_public():
    assert _client().get("/healthz").status_code == 200
