#!/usr/bin/env python3
"""
Тестовый скрипт для проверки логирования consumer.
Запускать после локального запуска всех сервисов.
"""

import asyncio
import json
import logging
from aiokafka import AIOKafkaProducer

# Настройки Kafka для локального тестирования
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
KAFKA_TOPIC_ADS = "ads"


async def send_test_event():
    """Отправляет тестовое событие в Kafka для проверки consumer."""

    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    logger.info("Starting test event sender")
    logger.info(f"Using Kafka bootstrap servers: {KAFKA_BOOTSTRAP_SERVERS}")
    logger.info(f"Sending to topic: {KAFKA_TOPIC_ADS}")

    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    try:
        await producer.start()
        logger.info("Kafka producer started successfully")

        # Отправляем тестовое событие ad.created
        test_event = {
            "event": "ad.created",
            "payload": {
                "ad_id": 999999  # Используем большой ID, чтобы не конфликтовать с реальными данными
            },
        }

        logger.info(f"Sending test event: {test_event}")
        await producer.send_and_wait(KAFKA_TOPIC_ADS, test_event)
        logger.info("Test event sent successfully")

        # Отправляем тестовое событие ad.deleted
        test_event = {"event": "ad.deleted", "payload": {"ad_id": 999999}}

        logger.info(f"Sending test event: {test_event}")
        await producer.send_and_wait(KAFKA_TOPIC_ADS, test_event)
        logger.info("Test event sent successfully")

    except Exception as e:
        logger.error(f"Error in test event sender: {e}")
    finally:
        await producer.stop()
        logger.info("Kafka producer stopped")


if __name__ == "__main__":
    asyncio.run(send_test_event())
