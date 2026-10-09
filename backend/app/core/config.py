"""全局配置管理

基于 pydantic-settings 从环境变量 / .env 文件加载配置，
提供类型安全、分组清晰的统一配置入口。
"""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===== 应用 =====
    app_name: str = "KnowFlow"
    app_env: str = "development"
    app_debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # ===== 数据库（MVP 默认 SQLite 单文件，无需外部服务）=====
    database_url: str = "sqlite+aiosqlite:///./knowflow.db"
    db_echo: bool = False
    # 以下两项仅 PostgreSQL 生效
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # ===== Redis =====
    redis_url: str = "redis://localhost:6379/0"

    # ===== ChromaDB =====
    chromadb_host: str = "localhost"
    chromadb_port: int = 8001

    # ===== MinIO =====
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "knowflow"
    minio_secure: bool = False

    # ===== JWT =====
    jwt_secret_key: str = "please-change-this"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440

    # ===== CORS =====
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # ===== 外部服务密钥 =====
    jina_api_key: str = ""

    # ===== LLM 多厂商配置 =====
    # 默认厂商：openai | custom | deepseek | moonshot | qwen | anthropic | ollama
    llm_default_provider: str = "openai"

    # --- 自定义中转站（任意 OpenAI 兼容服务）---
    # 适用于第三方 API 中转站、代理服务、自建网关等
    custom_api_key: str = ""
    custom_base_url: str = ""
    custom_model_fast: str = ""
    custom_model_balanced: str = ""
    custom_model_quality: str = ""
    custom_embedding_model: str = ""

    # --- OpenAI 官方 ---
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    # --- DeepSeek ---
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # --- Moonshot (Kimi) ---
    moonshot_api_key: str = ""
    moonshot_base_url: str = "https://api.moonshot.cn/v1"

    # --- 通义千问 (DashScope OpenAI 兼容接口) ---
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # --- Anthropic ---
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com"

    # --- Ollama (本地部署，无需 key) ---
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_api_key: str = "ollama"  # 占位符，Ollama 不校验

    # ===== 全局模型名称覆盖（可选，留空使用厂商默认模型）=====
    llm_model_fast: str = ""
    llm_model_balanced: str = ""
    llm_model_quality: str = ""
    llm_embedding_model: str = "text-embedding-3-small"

    # ===== 自生长 LLM Wiki =====
    llm_wiki_enabled: bool = True
    llm_wiki_publish_threshold: int = Field(default=5, ge=1)

    # ===== Celery =====
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例"""
    return Settings()


settings = get_settings()
