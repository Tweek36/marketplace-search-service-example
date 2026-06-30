from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
        use_enum_values=True,
        env_nested_delimiter="__",
    )

    # Database settings
    postgres_database_name: str = "search_db"
    postgres_host: str = "search-postgres"
    postgres_port: int = 5432
    postgres_username: str = "postgres"
    postgres_password: str = "postgres"

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_username}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_database_name}"

    kafka_bootstrap_servers: str = Field(
        default="redpanda:9092", alias="KAFKA_BOOTSTRAP_SERVERS"
    )
    kafka_topic_ads: str = Field(default="ads", alias="KAFKA_TOPIC_ADS")
    kafka_consumer_group: str = Field(
        default="search-service", alias="KAFKA_CONSUMER_GROUP"
    )
    ad_service_url: str = Field(
        default="http://ad-service:8002", alias="AD_SERVICE_URL"
    )
