import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import User, init_db


@pytest.fixture
def client():
    return TestClient(app)


def test_firebase_login_endpoint_returns_token(monkeypatch, client):
    init_db()
    db = SessionLocal()
    try:
        db.query(User).filter(User.username == "firebase_test_user").delete()
        db.commit()

        db_user = User(
            username="firebase_test_user",
            email="firebase_test@example.com",
            hashed_password="firebase_authenticated_user",
            role="user",
            current_balance=0.0,
            monthly_income=0.0,
            points=50,
            streak_days=0,
            financial_health_score=100,
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    finally:
        db.close()

    monkeypatch.setattr(
        "app.auth.verify_firebase_token",
        lambda token: {
            "firebase_uid": "firebase-123",
            "email": "firebase_test@example.com",
            "name": "Firebase Test",
        },
    )

    response = client.post("/auth/firebase-login", json={"idToken": "fake-token"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["username"] == "firebase_test_user"
