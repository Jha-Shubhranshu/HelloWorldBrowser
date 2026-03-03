"""
core/config.py
--------------
Centralised settings loaded from .env
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str

    # Pinecone
    pinecone_api_key: str
    pinecone_index:   str = "helloworld"
    pinecone_cloud:   str = "aws"
    pinecone_region:  str = "us-east-1"

    # Models
    embedding_model: str = "text-embedding-3-small"
    embedding_dim:   int = 1536
    chat_model:      str = "gpt-4o-mini"

    # Query defaults
    top_k_default: int = 5

    # CORS
    frontend_origin: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()