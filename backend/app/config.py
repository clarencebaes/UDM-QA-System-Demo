from urllib.parse import quote

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "udm_qa_demo"
    # Managed MySQL providers (e.g. Aiven) require TLS. Set MYSQL_SSL_CA to the
    # path of the CA certificate they give you, or MYSQL_SSL=true to use the
    # system trust store. Leave unset for a local XAMPP MySQL.
    mysql_ssl: bool = False
    mysql_ssl_ca: str = ""
    # Some managed providers do not allow CREATE DATABASE. Set to skip that step.
    mysql_skip_create_db: bool = False
    # Connection pool sizing. Managed free tiers cap connections (Aiven = 76),
    # so keep this small to avoid "too many connections" under a burst.
    db_pool_size: int = 5
    db_max_overflow: int = 5
    mysql_connect_timeout: int = 10
    mysql_read_timeout: int = 30
    mysql_write_timeout: int = 30
    # Compatibility endpoints are disabled for normal deployments. Only legacy regression fixtures enable this.
    legacy_submission_api: bool = False
    jwt_secret: str = "udm-qa-local-dev-change-me"
    jwt_expire_hours: int = 12
    cors_origins: str = "http://localhost:5173"

    def _ssl_args(self) -> dict:
        """Return PyMySQL SSL connect args, or an empty dict for plain TCP."""
        if not self.mysql_ssl:
            return {}
        if self.mysql_ssl_ca:
            return {"ssl": {"ca": self.mysql_ssl_ca}}
        # No CA path given: use an empty ssl dict, which makes PyMySQL validate
        # the server cert against the system trust store.
        return {"ssl": {}}

    @property
    def connect_args(self) -> dict:
        return {
            **self._ssl_args(),
            "connect_timeout": self.mysql_connect_timeout,
            "read_timeout": self.mysql_read_timeout,
            "write_timeout": self.mysql_write_timeout,
        }

    @property
    def database_url(self) -> str:
        user = quote(self.mysql_user, safe="")
        if self.mysql_password:
            auth = f"{user}:{quote(self.mysql_password, safe='')}"
        else:
            auth = user
        return (
            f"mysql+pymysql://{auth}@{self.mysql_host}:{self.mysql_port}/"
            f"{self.mysql_database}?charset=utf8mb4"
        )

    @property
    def server_url(self) -> str:
        user = quote(self.mysql_user, safe="")
        if self.mysql_password:
            auth = f"{user}:{quote(self.mysql_password, safe='')}"
        else:
            auth = user
        return f"mysql+pymysql://{auth}@{self.mysql_host}:{self.mysql_port}/?charset=utf8mb4"

    def cors_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
