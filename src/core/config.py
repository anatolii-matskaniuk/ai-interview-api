from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str

    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    OPENAI_API_KEY: str
    OPENAI_BASE_URL: str

    QUESTIONS_PER_SESSION: int = 5
    WEBSOCKET_ANSWER_TIMEOUT_SECONDS: int = 180

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
