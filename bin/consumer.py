import asyncio
import json
import logging
import os

import httpx
from aiokafka import AIOKafkaConsumer

from src.application.services.kafka_ads_consumer import KafkaAdsConsumer
from src.application.usecases.index_ad import IndexAd
from src.application.usecases.remove_ad import RemoveAd
from src.infrastructure.http.ad_client import AdServiceAdSource
from src.infrastructure.persistence.database import (
    create_engine,
    create_session_factory,
)
from src.infrastructure.persistence.uow import SQLAlchemyUnitOfWork
from src.settings import Settings


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    # Явно читаем переменную окружения AD_SERVICE_URL
    ad_service_url = os.getenv("AD_SERVICE_URL", "http://ad-service:8002")
    settings = Settings()
    # Переопределяем значение из переменной окружения
    settings.ad_service_url = ad_service_url
    logging.info(f"Kafka bootstrap servers: {settings.kafka_bootstrap_servers}")
    logging.info(f"Kafka topic ads: {settings.kafka_topic_ads}")
    logging.info(f"Kafka consumer group: {settings.kafka_consumer_group}")
    logging.info(f"Ad service URL: {settings.ad_service_url}")
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    consumer = AIOKafkaConsumer(
        settings.kafka_topic_ads,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_consumer_group,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    await consumer.start()

    async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
        ad_source = AdServiceAdSource(client, settings.ad_service_url)
        uow = SQLAlchemyUnitOfWork(session_factory)
        ads_consumer = KafkaAdsConsumer(
            consumer=consumer,
            index_ad=IndexAd(uow, ad_source),
            remove_ad=RemoveAd(uow),
        )
        try:
            await ads_consumer.run()
        finally:
            await consumer.stop()
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
