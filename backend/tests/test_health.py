def test_health_endpoint(client):
    data = client.get("/api/health").json()
    assert data["status"] == "ok"
    assert data["db"] == "ok"
    assert data["nlp_mode"] == "rules"
    assert data["kb_size"] >= 26


def test_docs_endpoint(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower() or "openapi" in response.text.lower()
