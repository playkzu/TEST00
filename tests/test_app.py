import pytest
from app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "保量建設" in text or "Hello" in text or "html" in text

def test_api_greet(client):
    response = client.get("/api/greet")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert "message" in data

def test_api_projects(client):
    response = client.get("/api/projects")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert data["count"] > 0
    assert len(data["data"]) > 0

def test_api_appointment_success(client):
    payload = {
        "name": "陳董事長",
        "gender": "先生",
        "phone": "0912-345-678",
        "email": "chen@example.com",
        "project": "保量・御峰",
        "date": "2026-10-15",
        "time_slot": "14:00 - 16:00",
        "budget": "1.5億以上",
        "notes": "希望了解頂樓景觀戶配置"
    }
    response = client.post("/api/appointment", json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert data["status"] == "success"
    assert "reservation_id" in data
    assert "VIP-BL" in data["reservation_id"]

def test_api_appointment_validation_error(client):
    payload = {
        "name": "張",
        "gender": "女士"
    }
    response = client.post("/api/appointment", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert data["status"] == "error"
    assert "errors" in data
