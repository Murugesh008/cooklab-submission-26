from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./app.db"
    secret_key: str = "changeme"
    gemini_api_key: str = ""
    access_token_expire_minutes: int = 1440
    algorithm: str = "HS256"

    class Config:
        env_file = ".env"


settings = Settings()
