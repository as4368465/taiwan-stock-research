import pytest
from app.core.enums import RiskType
from app.main import create_app
from app.services.risk_service import calculate_risk_score, classify_risk_score
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
def client() -> TestClient:
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    test_app = create_app(test_engine, test_session_factory)
    with TestClient(test_app) as test_client:
        yield test_client


def register_and_login(client: TestClient, email: str = "learner@example.com") -> str:
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "safe-password-123", "full_name": "測試使用者"},
    )
    assert registered.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "safe-password-123"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def test_register_succeeds_and_duplicate_email_is_blocked(client: TestClient) -> None:
    user = {
        "email": "learner@example.com",
        "password": "safe-password-123",
        "full_name": "測試使用者",
    }

    first = client.post("/api/v1/auth/register", json=user)
    duplicate = client.post(
        "/api/v1/auth/register",
        json={**user, "email": "LEARNER@example.com"},
    )

    assert first.status_code == 201
    assert first.json()["email"] == "learner@example.com"
    assert "hashed_password" not in first.json()
    assert duplicate.status_code == 409


def test_registration_validates_email_and_password_length(client: TestClient) -> None:
    short_password = client.post(
        "/api/v1/auth/register",
        json={"email": "valid@example.com", "password": "short", "full_name": "User"},
    )
    malformed_email = client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "safe-password-123", "full_name": "User"},
    )

    assert short_password.status_code == 422
    assert malformed_email.status_code == 422


def test_wrong_password_returns_401(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "learner@example.com", "password": "safe-password-123", "full_name": "測試使用者"},
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "learner@example.com", "password": "incorrect-password"},
    )

    assert response.status_code == 401


def test_jwt_protects_user_and_risk_routes(client: TestClient) -> None:
    unauthorized_me = client.get("/api/v1/auth/me")
    unauthorized_profile = client.get("/api/v1/risk/profile")
    token = register_and_login(client)
    authorized_me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert unauthorized_me.status_code == 401
    assert unauthorized_profile.status_code == 401
    assert authorized_me.status_code == 200
    assert authorized_me.json()["full_name"] == "測試使用者"
    assert authorized_me.json()["risk_type"] is None


def test_user_can_submit_five_answers_and_adjust_recommendations(client: TestClient) -> None:
    token = register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    questions = client.get("/api/v1/risk/questions")
    answers = {
        "experience_years": 1,
        "loss_tolerance": 1,
        "investment_goal": 1,
        "market_drop_reaction": 1,
        "investment_horizon": 1,
    }

    assessed = client.post(
        "/api/v1/risk/assess",
        headers=headers,
        json={"answers": answers},
    )
    adjusted = client.post(
        "/api/v1/risk/assess",
        headers=headers,
        json={"answers": answers, "target_return_pct": 7.5, "max_drawdown_pct": 4.5},
    )
    profile = client.get("/api/v1/risk/profile", headers=headers)

    assert questions.status_code == 200
    assert len(questions.json()["questions"]) == 5
    assert assessed.status_code == 200
    assert assessed.json()["risk_score"] == 5
    assert assessed.json()["risk_type"] == RiskType.CONSERVATIVE.value
    assert assessed.json()["suggested_target_return_min_pct"] == 6.0
    assert adjusted.json()["id"] == assessed.json()["id"]
    assert adjusted.json()["target_return_pct"] == 7.5
    assert adjusted.json()["max_drawdown_pct"] == 4.5
    assert profile.json()["risk_type"] == RiskType.CONSERVATIVE.value


@pytest.mark.parametrize(
    ("score", "expected_type"),
    [
        (5, RiskType.CONSERVATIVE),
        (11, RiskType.CONSERVATIVE),
        (12, RiskType.MODERATE),
        (18, RiskType.MODERATE),
        (19, RiskType.AGGRESSIVE),
        (25, RiskType.AGGRESSIVE),
    ],
)
def test_risk_classification_boundaries(score: int, expected_type: RiskType) -> None:
    assert classify_risk_score(score) is expected_type


def test_score_requires_exactly_five_answers() -> None:
    with pytest.raises(ValueError, match="完整回答"):
        calculate_risk_score({"experience_years": 1})
