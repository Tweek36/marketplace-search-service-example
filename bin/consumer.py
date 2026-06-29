import asyncio
import json
import logging
import os
from logging import getLogger

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

logger = getLogger(__name__)

# Жестко заданные параметры для прод окружения
KAFKA_BOOTSTRAP_SERVERS = "kafka.kafka-topic.svc:9092"
KAFKA_TOPIC_ADS = "Tweek36-marketplace.ads"
KAFKA_CONSUMER_GROUP = "search-service"
AD_SERVICE_URL = "http://student-tweek36-marketplace-ad-service-web.student-tweek36-marketplace-ad-service.svc:8000"


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Starting search-service consumer")
    logger.info(f"Using Kafka bootstrap servers: {KAFKA_BOOTSTRAP_SERVERS}")
    logger.info(f"Listening to topic: {KAFKA_TOPIC_ADS}")
    logger.info(f"Consumer group: {KAFKA_CONSUMER_GROUP}")
    logger.info(f"Ad service URL: {AD_SERVICE_URL}")

    settings = Settings()
    try:
        engine = create_engine(settings)
        session_factory = create_session_factory(engine)
        logger.info("Database connection established successfully")
    except Exception as e:
        logger.error(f"Failed to establish database connection: {e}")
        raise

    # Используем жестко заданные параметры для прод окружения
    try:
        logger.info("Initializing Kafka consumer...")
        consumer = AIOKafkaConsumer(
            KAFKA_TOPIC_ADS,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=KAFKA_CONSUMER_GROUP,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        )
        await consumer.start()
        logger.info("Kafka consumer started successfully")
    except Exception as e:
        logger.error(f"Failed to start Kafka consumer: {e}")
        raise

    async with httpx.AsyncClient(timeout=30.0) as client:
        ad_source = AdServiceAdSource(client, AD_SERVICE_URL)
        uow = SQLAlchemyUnitOfWork(session_factory)
        ads_consumer = KafkaAdsConsumer(
            consumer=consumer,
            index_ad=IndexAd(uow, ad_source),
            remove_ad=RemoveAd(uow),
        )

        logger.info("Starting message processing loop...")
        try:
            await ads_consumer.run()
        except Exception as e:
            logger.error(f"Error in consumer loop: {e}")
            raise
        finally:
            logger.info("Stopping consumer...")
            await consumer.stop()
            await engine.dispose()
            logger.info("Consumer stopped successfully")


if __name__ == "__main__":
    asyncio.run(main())
