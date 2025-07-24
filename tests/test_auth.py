import pytest
from httpx import AsyncClient


@pytest.fixture
def auth_url() -> str:
    return "/api/v1/auth"


@pytest.mark.parametrize(
    ("email", "password", "status_code"),
    [
        ("testuser@example.com", "supersecret", 201),
        ("invalid-email", "supersecret", 422),
        (None, "supersecret", 422),
    ]
)
async def test_register(
        async_client: AsyncClient,
        auth_url: str,
        email: str,
        password: str,
        status_code: int
):
    response = await async_client.post(
        f"{auth_url}/register",
        json={"email": email, "password": password}
    )
    assert response.status_code == status_code


async def test_login_after_registration(async_client: AsyncClient, auth_url: str):
    email = "logintest@example.com"
    password = "correct_password"

    register_response = await async_client.post(
        f"{auth_url}/register",
        json={"email": email, "password": password}
    )
    assert register_response.status_code == 201

    login_response = await async_client.post(
        f"{auth_url}/login",
        data={"username": email, "password": password}
    )
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
