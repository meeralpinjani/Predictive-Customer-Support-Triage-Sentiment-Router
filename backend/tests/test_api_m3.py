from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_post_and_get_ticket():
    # Submit ticket matching Demo Scenario 1
    payload = {
        "customer_id": "c1",
        "subject": "Production dashboard DOWN",
        "body": "Our production dashboard is DOWN. This is unacceptable, we will cancel if this is not fixed ASAP!",
        "channel": "web",
    }
    response = client.post("/api/tickets", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["route"] == "senior"
    assert "outage" in data["analysis"]["critical_flags"]
    assert data["customer"]["segment"] == "enterprise"
    assert data["priority"] >= 60
    assert data["route_reason"] == "Critical rule: outage"

    # Retrieve by ID
    ticket_id = data["id"]
    get_res = client.get(f"/api/tickets/{ticket_id}")
    assert get_res.status_code == 200
    detail = get_res.json()
    assert detail["id"] == ticket_id
    assert detail["priority"] == data["priority"]
    assert detail["route"] == "senior"

    # List tickets sorted by priority
    list_res = client.get("/api/tickets?sort=priority")
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) > 0
    # verify priority desc
    for i in range(len(items) - 1):
        assert items[i]["priority"] >= items[i + 1]["priority"]
