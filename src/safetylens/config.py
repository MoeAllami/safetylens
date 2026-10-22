"""Settings read from the environment and `.env`.

Why: model names, budget and paths come from one place so nothing is hard-coded, and the API key
is a SecretStr so printing or logging a Settings object cannot leak it.
"""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SAFETYLENS_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    planner_model: str = ""
    writer_model: str = ""
    daily_budget_usd: float = 0.0
    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    embed_model: str = "BAAI/bge-small-en-v1.5"
    embed_batch_size: int = 128
    embed_device: str = "auto"  # "auto" picks CUDA when available, else CPU
    rerank_model: str = "BAAI/bge-reranker-base"
    rerank_depth: int = 20  # chosen on dev queries only (20: 0.775, 30: 0.739, 50: 0.683)
