from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Environment
    environment: Literal["local", "kubernetes"] = "local"

    postgres_host: str
    postgres_database_name: str
    postgres_password: str
    postgres_port: int
    postgres_username: str

    # Kafka configuration
    jwt_algorithm: str = "HS256"
    kafka_bootstrap_servers: str | None = None
    kafka_brokers: str | None = None
    kafka_topic_ads: str | None = None
    kafka_topic_marketplace_ads: str | None = None
    kafka_consumer_group: str = "search-service"

    # Ad service
    ad_service_url: str | None = None

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_username}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_database_name}"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Use KAFKA_BROKERS if provided (fallback to KAFKA_BOOTSTRAP_SERVERS)
        if self.kafka_brokers:
            self.kafka_bootstrap_servers = self.kafka_brokers
        elif not self.kafka_bootstrap_servers:
            raise ValueError(
                "Either KAFKA_BROKERS or KAFKA_BOOTSTRAP_SERVERS must be provided"
            )

        # Use KAFKA_TOPIC_MARKETPLACE_ADS if provided (fallback to KAFKA_TOPIC_ADS)
        if self.kafka_topic_marketplace_ads:
            self.kafka_topic_ads = self.kafka_topic_marketplace_ads
        elif not self.kafka_topic_ads:
            raise ValueError(
                "Either KAFKA_TOPIC_MARKETPLACE_ADS or KAFKA_TOPIC_ADS must be provided"
            )
