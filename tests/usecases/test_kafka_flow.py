import logging

import pytest

from src.application.services.kafka_ads_consumer import KafkaAdsConsumer
from src.application.usecases.index_ad import IndexAd
from src.application.usecases.remove_ad import RemoveAd
from src.application.usecases.search import Search
from tests.conftest import FakeAdSource, FakeUnitOfWork, make_snapshot

# Настроим логирование для тестов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FakeKafkaConsumer:
    def __init__(self, messages):
        self.messages = messages
        self.committed = False

    async def __aiter__(self):
        for msg in self.messages:
            yield msg

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_kafka_flow_normal(
    fake_uow: FakeUnitOfWork,
    fake_ad_source: FakeAdSource,
) -> None:
    """Тест симулирует нормальный поток Kafka событий"""
    ad_id = 47

    # Создаем consumer с фейковыми зависимостями
    consumer = KafkaAdsConsumer(
        consumer=FakeKafkaConsumer(
            [
                type(
                    "Message",
                    (),
                    {"value": {"event": "ad.created", "payload": {"ad_id": ad_id}}},
                )
            ]
        ),
        index_ad=IndexAd(fake_uow, fake_ad_source),
        remove_ad=RemoveAd(fake_uow),
    )

    # Настраиваем AdSource - возвращаем активное объявление
    fake_ad_source.set(
        make_snapshot(ad_id=ad_id, title="autotest123 table", status="active")
    )

    # Запускаем consumer - обрабатываем событие ad.created
    await consumer.run()

    # Проверяем, что объявление проиндексировано
    docs = fake_uow.search.snapshot()
    logger.info("After ad.created: %s", docs)
    assert ad_id in docs

    # Теперь симулируем событие ad.deleted
    consumer = KafkaAdsConsumer(
        consumer=FakeKafkaConsumer(
            [
                type(
                    "Message",
                    (),
                    {"value": {"event": "ad.deleted", "payload": {"ad_id": ad_id}}},
                )
            ]
        ),
        index_ad=IndexAd(fake_uow, fake_ad_source),
        remove_ad=RemoveAd(fake_uow),
    )

    # Запускаем consumer - обрабатываем событие ad.deleted
    await consumer.run()

    # Проверяем, что объявление удалено
    docs = fake_uow.search.snapshot()
    logger.info("After ad.deleted: %s", docs)
    assert ad_id not in docs

    # Проверяем поиск
    search_results, total = await Search(fake_uow).execute(
        query="autotest123",
        category=None,
        city=None,
        min_price=None,
        max_price=None,
        sort=None,
        limit=20,
        offset=0,
    )
    logger.info("Search results: %s, total: %s", search_results, total)
    assert total == 0
    assert ad_id not in [doc.ad_id for doc in search_results]


@pytest.mark.asyncio
async def test_kafka_flow_out_of_order(
    fake_uow: FakeUnitOfWork,
    fake_ad_source: FakeAdSource,
) -> None:
    """Тест симулирует ситуацию, когда события приходят не по порядку"""
    ad_id = 47

    # Настраиваем AdSource - возвращаем активное объявление
    fake_ad_source.set(
        make_snapshot(ad_id=ad_id, title="autotest123 table", status="active")
    )

    # Создаем consumer с фейковыми зависимостями
    # Сначала приходит событие ad.deleted, затем ad.created
    consumer = KafkaAdsConsumer(
        consumer=FakeKafkaConsumer(
            [
                type(
                    "Message",
                    (),
                    {"value": {"event": "ad.deleted", "payload": {"ad_id": ad_id}}},
                ),
                type(
                    "Message",
                    (),
                    {"value": {"event": "ad.created", "payload": {"ad_id": ad_id}}},
                ),
            ]
        ),
        index_ad=IndexAd(fake_uow, fake_ad_source),
        remove_ad=RemoveAd(fake_uow),
    )

    # Запускаем consumer - обрабатываем оба события
    await consumer.run()

    # После ad.deleted объявление должно быть удалено
    # После ad.created объявление не должно быть проиндексировано повторно, так как оно было недавно удалено  # noqa: E501
    docs = fake_uow.search.snapshot()
    logger.info("After out-of-order events: %s", docs)
    assert ad_id not in docs  # Объявление не должно быть проиндексировано повторно

    # Проверяем поиск - объявление не должно быть проиндексировано повторно
    search_results, total = await Search(fake_uow).execute(
        query="autotest123",
        category=None,
        city=None,
        min_price=None,
        max_price=None,
        sort=None,
        limit=20,
        offset=0,
    )
    logger.info("Search results: %s, total: %s", search_results, total)
    assert total == 0
    assert ad_id not in [doc.ad_id for doc in search_results]


@pytest.mark.asyncio
async def test_kafka_flow_deleted_then_archived(
    fake_uow: FakeUnitOfWork,
    fake_ad_source: FakeAdSource,
) -> None:
    """Тест симулирует ситуацию: удаление → событие с архивным статусом"""
    ad_id = 47

    # Настраиваем AdSource - возвращаем активное объявление
    fake_ad_source.set(
        make_snapshot(ad_id=ad_id, title="autotest123 table", status="active")
    )

    # Создаем consumer с фейковыми зависимостями
    consumer = KafkaAdsConsumer(
        consumer=FakeKafkaConsumer(
            [
                type(
                    "Message",
                    (),
                    {"value": {"event": "ad.created", "payload": {"ad_id": ad_id}}},
                )
            ]
        ),
        index_ad=IndexAd(fake_uow, fake_ad_source),
        remove_ad=RemoveAd(fake_uow),
    )

    # Запускаем consumer - обрабатываем событие ad.created
    await consumer.run()

    # Проверяем, что объявление проиндексировано
    docs = fake_uow.search.snapshot()
    logger.info("After ad.created: %s", docs)
    assert ad_id in docs

    # Теперь симулируем событие ad.deleted
    consumer = KafkaAdsConsumer(
        consumer=FakeKafkaConsumer(
            [
                type(
                    "Message",
                    (),
                    {"value": {"event": "ad.deleted", "payload": {"ad_id": ad_id}}},
                )
            ]
        ),
        index_ad=IndexAd(fake_uow, fake_ad_source),
        remove_ad=RemoveAd(fake_uow),
    )

    # Запускаем consumer - обрабатываем событие ad.deleted
    await consumer.run()

    # Проверяем, что объявление удалено
    docs = fake_uow.search.snapshot()
    logger.info("After ad.deleted: %s", docs)
    assert ad_id not in docs

    # Теперь симулируем событие ad.updated с архивным статусом
    # Настраиваем AdSource - возвращаем архивное объявление
    fake_ad_source.set(
        make_snapshot(ad_id=ad_id, title="autotest123 table", status="archived")
    )

    consumer = KafkaAdsConsumer(
        consumer=FakeKafkaConsumer(
            [
                type(
                    "Message",
                    (),
                    {"value": {"event": "ad.updated", "payload": {"ad_id": ad_id}}},
                )
            ]
        ),
        index_ad=IndexAd(fake_uow, fake_ad_source),
        remove_ad=RemoveAd(fake_uow),
    )

    # Запускаем consumer - обрабатываем событие ad.updated
    await consumer.run()

    # Проверяем, что объявление остается удаленным
    docs = fake_uow.search.snapshot()
    logger.info("After ad.updated with archived status: %s", docs)
    assert ad_id not in docs

    # Проверяем поиск
    search_results, total = await Search(fake_uow).execute(
        query="autotest123",
        category=None,
        city=None,
        min_price=None,
        max_price=None,
        sort=None,
        limit=20,
        offset=0,
    )
    logger.info("Search results: %s, total: %s", search_results, total)
    assert total == 0
    assert ad_id not in [doc.ad_id for doc in search_results]
