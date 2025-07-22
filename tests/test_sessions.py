from unittest.mock import patch, AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.interviews.models import InterviewSession
from src.auth.models import User
from src.auth.service import AuthService


@pytest.fixture
def sessions_url() -> str:
    return "/api/v1/sessions/"


@pytest.fixture
async def specific_user(async_client: AsyncClient, test_db_session: AsyncSession) -> User:
    email = "testuser@example.com"
    password = "password123"

    auth_service = AuthService()
    user = await auth_service.get_by_email(db=test_db_session, email=email)
    if not user:
        await async_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password},
        )
        user = await auth_service.get_by_email(db=test_db_session, email=email)
    return user


@pytest.fixture
async def specific_user_auth_headers(async_client: AsyncClient, specific_user: User) -> dict:
    login_response = await async_client.post(
        "/api/v1/auth/login", data={"username": specific_user.email, "password": "password123"}
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def active_session(test_db_session: AsyncSession, specific_user: User) -> InterviewSession:
    session = InterviewSession(user_id=specific_user.id, topic="Existing Topic", status='active')
    test_db_session.add(session)
    await test_db_session.commit()
    await test_db_session.refresh(session)
    return session


@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({"topic": "Python"}, 202),
        ({}, 422),
    ],
)
@patch("src.auth.service.TokenService.is_token_blacklisted", new_callable=AsyncMock)
@patch("src.tasks.generation.generate_questions_for_session.delay")
async def test_create_session(
        mock_celery_delay,
        mock_is_token_blacklisted,
        async_client: AsyncClient,
        sessions_url: str,
        specific_user_auth_headers: dict,
        payload: dict,
        expected_status: int
):
    mock_is_token_blacklisted.return_value = False
    mock_celery_delay.return_value = None

    response = await async_client.post(
        sessions_url,
        headers=specific_user_auth_headers,
        json=payload,
    )

    assert response.status_code == expected_status
    if response.status_code == 202:
        data = response.json()
        assert "id" in data
        assert data["topic"] == payload["topic"]
        mock_celery_delay.assert_called_once()
    else:
        mock_celery_delay.assert_not_called()


@patch("src.auth.service.TokenService.is_token_blacklisted", new_callable=AsyncMock)
async def test_get_all_sessions(
        mock_is_token_blacklisted,
        async_client: AsyncClient,
        sessions_url: str,
        specific_user_auth_headers: dict,
        active_session: InterviewSession,
):
    mock_is_token_blacklisted.return_value = False

    response = await async_client.get(sessions_url, headers=specific_user_auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["id"] == str(active_session.id)


@patch("src.auth.service.TokenService.is_token_blacklisted", new_callable=AsyncMock)
async def test_get_single_session(
        mock_is_token_blacklisted,
        async_client: AsyncClient,
        sessions_url: str,
        specific_user_auth_headers: dict,
        active_session: InterviewSession,
):
    mock_is_token_blacklisted.return_value = False

    get_resp = await async_client.get(
        f"{sessions_url}{active_session.id}",
        headers=specific_user_auth_headers
    )

    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == str(active_session.id)
    assert data["status"] == "active"


async def test_protected_routes_require_auth(
        async_client: AsyncClient,
        sessions_url: str,
):
    resp_post = await async_client.post(sessions_url, json={"topic": "Unauthorized"})
    resp_get = await async_client.get(sessions_url)

    assert resp_post.status_code == 401
    assert resp_get.status_code == 401
