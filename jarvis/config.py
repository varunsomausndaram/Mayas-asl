"""Typed runtime configuration for Jarvis.

Settings are loaded in this order of precedence:

1. Arguments passed to :class:`Settings` (tests and programmatic use).
2. Environment variables — the canonical production surface.
3. A ``.env`` file in the current working directory, if present.
4. The defaults declared below.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration object.

    Every knob Jarvis exposes lives here. Consumers pull their configuration
    from an instance of this class rather than reading ``os.environ`` directly
    so that tests can build an isolated configuration and so that a single
    mis-spelled env var fails loudly at startup.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ server
    host: str = Field(default="0.0.0.0", alias="JARVIS_HOST")
    port: int = Field(default=8765, alias="JARVIS_PORT")
    log_level: str = Field(default="INFO", alias="JARVIS_LOG_LEVEL")
    reload: bool = Field(default=False, alias="JARVIS_RELOAD")
    data_dir: Path = Field(default=Path("./var"), alias="JARVIS_DATA_DIR")
    cors_origins: str = Field(default="*", alias="JARVIS_CORS_ORIGINS")

    # -------------------------------------------------------------------- auth
    api_key: str = Field(default="change-me", alias="JARVIS_API_KEY")

    # ---------------------------------------------------------------- llm core
    llm_provider: str = Field(default="ollama", alias="JARVIS_LLM_PROVIDER")
    llm_fallback: str | None = Field(default=None, alias="JARVIS_LLM_FALLBACK")
    llm_max_tokens: int = Field(default=2048, alias="JARVIS_LLM_MAX_TOKENS")
    llm_temperature: float = Field(default=0.3, alias="JARVIS_LLM_TEMPERATURE")

    # -------------------------------------------------------------- llm: ollama
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="gemma2:2b", alias="OLLAMA_MODEL")

    # ----------------------------------------------------------- llm: anthropic
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-4-6", alias="ANTHROPIC_MODEL")

    # -------------------------------------------------------------- llm: openai
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    # ------------------------------------------------------------------- github
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    github_default_owner: str = Field(default="", alias="GITHUB_DEFAULT_OWNER")

    # ----------------------------------------------------------- claude code
    claude_code_cli: str = Field(default="claude", alias="CLAUDE_CODE_CLI")
    claude_code_workspaces: Path = Field(
        default=Path("./var/workspaces"), alias="CLAUDE_CODE_WORKSPACES"
    )
    claude_code_timeout: int = Field(default=1800, alias="CLAUDE_CODE_TIMEOUT")

    # ------------------------------------------------------------------- voice
    voice_enabled: bool = Field(default=True, alias="JARVIS_VOICE_ENABLED")
    whisper_model: str = Field(default="base", alias="JARVIS_WHISPER_MODEL")
    tts_rate: int = Field(default=180, alias="JARVIS_TTS_RATE")
    tts_voice: str = Field(default="", alias="JARVIS_TTS_VOICE")

    # ------------------------------------------------------- tool permissions
    allowed_tools: str = Field(
        default=(
            "filesystem_read,filesystem_write,web_search,web_fetch,"
            "github_list_repos,github_get_file,github_create_issue,"
            "system_info,notify,claude_code_dispatch"
        ),
        alias="JARVIS_ALLOWED_TOOLS",
    )

    # ------------------------------------------------------------------ shell
    shell_enabled: bool = Field(default=False, alias="JARVIS_SHELL_ENABLED")
    shell_allowlist: str = Field(
        default="ls,pwd,echo,cat,git,python,python3,pip,node,npm,make",
        alias="JARVIS_SHELL_ALLOWLIST",
    )
    shell_timeout: int = Field(default=60, alias="JARVIS_SHELL_TIMEOUT")

    # ---------------------------------------------------------------- validators
    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, v: str) -> str:
        level = v.upper().strip()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"invalid log level: {v!r}")
        return level

    @field_validator("llm_provider", "llm_fallback")
    @classmethod
    def _validate_provider(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.lower().strip()
        if v not in {"ollama", "anthropic", "openai", "echo"}:
            raise ValueError(f"unknown LLM provider: {v!r}")
        return v

    # ------------------------------------------------------------------ helpers
    def cors_list(self) -> list[str]:
        """Parse :attr:`cors_origins` into a list for FastAPI's CORS middleware."""
        raw = (self.cors_origins or "").strip()
        if raw == "*" or raw == "":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    def allowed_tool_set(self) -> set[str]:
        """Parsed allowlist of tool names (``*`` means all)."""
        raw = (self.allowed_tools or "").strip()
        if raw == "*":
            return {"*"}
        return {n.strip() for n in raw.split(",") if n.strip()}

    def shell_allowed(self) -> set[str]:
        return {c.strip() for c in self.shell_allowlist.split(",") if c.strip()}

    def ensure_dirs(self) -> None:
        """Create on-disk directories the runtime writes to."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "logs").mkdir(parents=True, exist_ok=True)
        self.claude_code_workspaces.mkdir(parents=True, exist_ok=True)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "jarvis.sqlite3"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide :class:`Settings`, cached after first access."""
    s = Settings()
    s.ensure_dirs()
    return s


def reload_settings() -> Settings:
    """Clear the cache and re-read settings. Useful in tests."""
    get_settings.cache_clear()
    return get_settings()
