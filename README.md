# 🤖 AI Interview API

A backend service for practicing technical interviews. It allows users to run simulated interviews on selected topics, receiving AI-generated questions and instant feedback on their answers via a real-time WebSocket connection.

---
## ✨ Key Features

* **Topic-Based Sessions:** Create interviews for specific topics (e.g., Python, SQL, FastAPI).
* **Dynamic Question Count:** Specify the desired number of questions for each session.
* **Real-time Interaction:** Full-duplex communication via **WebSockets** for instant question delivery and result notifications.
* **Asynchronous Processing:** Utilizes **Celery** and **Redis** for background question generation and answer evaluation without blocking the user.
* **AI-Powered Evaluation:** Integrates with the **OpenAI API** to provide objective scores and helpful feedback.
* **Authentication:** Secure endpoints using JWT (register, login, token refresh).
* **Detailed Statistics:** An endpoint to retrieve aggregated statistics for all completed sessions.

---
## 🛠️ Tech Stack

* **Framework:** FastAPI
* **Database:** PostgreSQL
* **ORM / Migrations:** SQLAlchemy (with `asyncpg`), Alembic
* **Background Tasks:** Celery
* **Message Broker / Cache:** Redis
* **Containerization:** Docker, Docker Compose
* **Testing:** Pytest
* **AI:** OpenAI API (gpt-4o)

---
## 🛠 Project Structure

```
├── .github/                # GitHub Actions (CI/CD) configuration
├── alembic/                # Alembic database migration scripts
│   └── versions/
├── src/                    # Main application source code
│   ├── auth/               # Authentication
│   ├── core/               # Application core: configuration, Celery setup
│   ├── db/                 # Everything related to the database (sessions, Base)
│   ├── interviews/         # Core business logic: interviews, questions, WebSocket
│   ├── shared/             # Shared utilities used across different modules
│   ├── tasks/              # Celery background tasks (question generation, answer evaluation)
│   └── main.py             # Main file, entry point for the FastAPI application
├── tests/                  # Directory for tests (pytest)
├── .dockerignore           # Files ignored during Docker image build
├── .env                    # Environment variables
├── .flake8                 # Configuration for the flake8 linter
├── .gitignore              # Files ignored by the Git version control system
├── .pre-commit-config.yaml # Configuration for pre-commit hooks
├── alembic.ini             # Configuration file for Alembic
├── docker-compose.yml      # File for orchestrating Docker containers (API, worker, db, redis)
├── Dockerfile              # Instructions for building the application's Docker image
├── pytest.ini              # Configuration file for Pytest
├── README.md               # This file
├── requirements.txt        # List of Python dependencies
└── start.sh                # Script to run the application inside the Docker container
```

---
## 🚀 Getting Started

To run the project locally, you will need Docker and Docker Compose installed.

### Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/anatolii-matskaniuk/ai-interview-api
    cd ai-interview-api
    ```

2.  **Create the `.env` file:**
    Create a `.env` file in the project root by copying the contents of `.env.example` and filling in your own values.

    **.env.example**
    ```env
    # PostgreSQL
    PG_USER=your_pg_user
    PG_PASSWORD=your_pg_password
    PG_DATABASE=your_pg_db
    DATABASE_URL=postgresql+asyncpg://${PG_USER}:${PG_PASSWORD}@db:5432/${PG_DATABASE}

    # Redis
    REDIS_URL=redis://redis:6379/0

    # JWT Auth
    SECRET_KEY=your_super_secret_key_for_jwt
    ALGORITHM=HS256
    ACCESS_TOKEN_EXPIRE_MINUTES=30

    # OpenAI
    OPENAI_API_KEY=sk-your-openai-api-key
    OPENAI_BASE_URL=https://api.openai-base-url.com/v1

    # Application Settings
    WEBSOCKET_ANSWER_TIMEOUT_SECONDS=180
    ```

3.  **Launch the project:**
    Run the following command to build and start all services in Docker containers.
    ```bash
    docker-compose up -d --build
    ```
    Once successfully launched, the API will be available at `http://localhost:8000`.
---
## 🧪 Testing

To run the automated tests, use the following Docker Compose command:
```bash
docker-compose exec api pytest
```
---
## 📘 Endpoints
The API provides a set of endpoints for user management, interview session control, and real-time communication.
### Auth
These endpoints handle user registration, login, and token management based on JWT.

| Method | Endpoint               | Description                                     | Auth Required |
|--------|------------------------|-------------------------------------------------|---------------|
| POST   | /api/v1/auth/register/ | Register a new user                             | No            |
| POST   | /api/v1/auth/login/    | Log in to receive JWT access and refresh tokens | No            |
| POST   | /api/v1/auth/logout/   | Log out and blacklist the current access token  | Yes           |
| POST   | /api/v1/auth/refresh/  | Get a new access token using a refresh token    | No(Cookies)   |
| GET    | /api/v1/auth/me/       | Get the current authenticated user's profile    | Yes           |

### Sessions
This group of endpoints allows for the creation and management of interview sessions.

| Method | Endpoint                       | Description                                        | Auth Required |
|--------|--------------------------------|----------------------------------------------------|---------------|
| POST   | /api/v1/sessions/              | Create a new interview session on a specific topic | Yes           |
| GET    | /api/v1/sessions/              | Get a list of all interview sessions for the user  | Yes           |
| GET    | /api/v1/sessions/{session_id}/ | Get details for a specific interview session       | Yes           |
| GET    | /api/v1/sessions/stats/        | Get aggregated performance statistics for the user | Yes           |

### WebSocket
This endpoint provides a real-time, full-duplex communication channel for conducting an interview.

| Method | Endpoint                             | Description                                     | Auth Required |
|--------|--------------------------------------|-------------------------------------------------|---------------|
| WS     | /ws/sessions/{session_id}?token=JWT  | Establish a WebSocket connection for a session  | Yes(Token)    |


---
## API Documentation
FastAPI automatically generates interactive documentation. It is available at the following URLs after launching the project:
* **Swagger UI:** `http://localhost:8000/docs`
* **ReDoc:** `http://localhost:8000/redoc`