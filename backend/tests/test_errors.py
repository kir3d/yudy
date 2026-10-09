from fastapi.testclient import TestClient

from app.main import app


def test_missing_route_has_consistent_error():
    response = TestClient(app).get("/missing")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "HTTP_404", "message": "Not Found"}}
