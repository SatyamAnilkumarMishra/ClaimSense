"""Central configuration using Pydantic Settings.

Reads from environment variables, .env file, or Streamlit secrets when available.
Enforces type safety and provides helper flags for live vs offline fallback mode.
"""

from functools import lru_cache
import os
from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Runtime & Deployment Mode
    BACKEND_MODE: str = Field(default="inprocess", description="'inprocess' for Streamlit monolithic, 'http' for FastAPI")
    OFFLINE_MODE: bool = Field(default=False, description="Force offline snapshot mode when True")

    # Databricks Configuration
    DATABRICKS_HOST: Optional[str] = Field(default=None, description="Workspace URL e.g. https://dbc-xxx.cloud.databricks.com")
    DATABRICKS_TOKEN: Optional[str] = Field(default=None, description="Personal Access Token")
    DATABRICKS_HTTP_PATH: Optional[str] = Field(default=None, description="SQL Warehouse HTTP Path")
    DATABRICKS_CATALOG: str = Field(default="workspace", description="Unity Catalog name")
    DATABRICKS_SCHEMA: str = Field(default="claimsense", description="Schema / database name")
    DATABRICKS_VOLUME: str = Field(default="landing_zone", description="Landing zone Volume name")
    DATABRICKS_JOB_ID: Optional[str] = Field(default=None, description="Workflow Job ID for pipeline execution")

    # Groq LLM Configuration
    GROQ_API_KEY: Optional[str] = Field(default=None, description="Groq API key")
    GROQ_FAST_MODEL: str = Field(default="llama-3.1-8b-instant", description="Fast low-latency model for extraction")
    GROQ_REASONING_MODEL: str = Field(default="llama-3.3-70b-versatile", description="Reasoning model for assessment")
    GROQ_DAILY_TOKEN_LIMIT: int = Field(default=100_000, description="Daily safety ceiling to guard free tier")

    # FastAPI REST & Security
    FASTAPI_API_KEY: str = Field(default="claimsense_dev_key_only_change_in_prod", description="Secret key for X-API-Key auth")
    FASTAPI_HOST: str = Field(default="127.0.0.1")
    FASTAPI_PORT: int = Field(default=8000)
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:8501", "http://127.0.0.1:8501"])

    # Snowflake Configuration (Optional - Stage 7)
    SNOWFLAKE_ACCOUNT: Optional[str] = None
    SNOWFLAKE_USER: Optional[str] = None
    SNOWFLAKE_PASSWORD: Optional[str] = None
    SNOWFLAKE_WAREHOUSE: str = "COMPUTE_WH"
    SNOWFLAKE_DATABASE: str = "CLAIMSENSE_DB"
    SNOWFLAKE_SCHEMA: str = "MART"
    SNOWFLAKE_ROLE: str = "ACCOUNTADMIN"

    # Paths
    BASE_PATH: Path = BASE_DIR
    SNAPSHOTS_PATH: Path = BASE_DIR / "snapshots"
    DATA_GEN_PATH: Path = BASE_DIR / "data_gen"

    @property
    def is_databricks_configured(self) -> bool:
        """Returns True only if all required Databricks connection parameters are present."""
        return bool(
            self.DATABRICKS_HOST
            and self.DATABRICKS_TOKEN
            and self.DATABRICKS_HTTP_PATH
            and not self.OFFLINE_MODE
        )

    @property
    def is_groq_configured(self) -> bool:
        """Returns True if Groq API key is populated."""
        return bool(self.GROQ_API_KEY and not self.OFFLINE_MODE)

    @property
    def is_snowflake_configured(self) -> bool:
        """Returns True if minimum Snowflake parameters are set."""
        return bool(
            self.SNOWFLAKE_ACCOUNT
            and self.SNOWFLAKE_USER
            and self.SNOWFLAKE_PASSWORD
            and not self.OFFLINE_MODE
        )


@lru_cache()
def get_settings() -> Settings:
    """Singleton getter for application settings."""
    # If running inside Streamlit with secrets, populate environment variables first
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            for k, v in st.secrets.items():
                if isinstance(v, str) and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass
    return Settings()
