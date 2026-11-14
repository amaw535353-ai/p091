"""Configuration is server controlled; external model APIs are deliberately absent."""
import os
from dataclasses import dataclass
from typing import Any


@dataclass
class Settings:
    mode: str = "offline"
    database_url: str = "sqlite:///work/lab.db"
    seed: bool = True
    issuer: str = "http://localhost:8081/realms/p091"
    audience: str = "p091-api"
    jwks_url: str = "http://localhost:8081/realms/p091/protocol/openid-connect/certs"
    openfga_url: str = "http://localhost:8082"
    fga_store_id: str = ""
    fga_model_id: str = ""
    fga_token: str = ""
    qdrant_url: str = "http://localhost:6333"
    qdrant_key: str = ""
    nextcloud_enabled: bool = False
    nextcloud_url: str = "http://localhost:8083"
    nextcloud_user: str = ""
    nextcloud_password: str = ""

    def __post_init__(self) -> None:
        if self.mode not in {"offline", "live"}:
            raise ValueError("LAB_MODE must be offline or live")
        if self.mode == "live" and not self.database_url.startswith("postgresql://"):
            raise ValueError("Live mode requires PostgreSQL")

    @classmethod
    def from_env(cls) -> "Settings":
        fields = {
            "mode": "LAB_MODE", "database_url": "DATABASE_URL",
            "issuer": "OIDC_ISSUER", "audience": "OIDC_AUDIENCE", "jwks_url": "OIDC_JWKS_URL",
            "openfga_url": "OPENFGA_URL", "fga_store_id": "FGA_STORE_ID", "fga_model_id": "FGA_MODEL_ID",
            "fga_token": "FGA_TOKEN", "qdrant_url": "QDRANT_URL", "qdrant_key": "QDRANT_KEY",
            "nextcloud_url": "NEXTCLOUD_URL", "nextcloud_user": "NEXTCLOUD_USER",
            "nextcloud_password": "NEXTCLOUD_PASSWORD",
        }
        values: dict[str, Any] = {field: os.environ[env] for field, env in fields.items() if env in os.environ}
        return cls(**values, nextcloud_enabled=os.getenv("NEXTCLOUD_ENABLED", "false").lower() == "true")
