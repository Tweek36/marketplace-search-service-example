import logging

import pytest

from src.application.usecases.index_ad import IndexAd
from src.application.usecases.remove_ad import RemoveAd
from src.application.usecases.search import Search
from tests.conftest import FakeAdSource, FakeUnitOfWork, make_snapshot

# Настроим логирование для тестов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_index_ad_after_remove_with_active_status(
    fake_uow: FakeUnitOfWork,
    fake_ad_source: FakeAdSource,
) -> None:
    """Тест проверяет, что происходит, если после удаления приходит событие с активным статусом"""  # noqa: E501
    ad_id = 47

    # 1. Создаем активное объявление
    fake_ad_source.set(make_snapshot(ad_id=ad_id, title="test table", status="active"))

    # 2. Индексируем объявление
    index_ad = IndexAd(fake_uow, fake_ad_source)
    await index_ad.execute(ad_id)
    docs = fake_uow.search.snapshot()
    logger.info("After indexing: %s", docs)
    assert ad_id in docs

    # 3. Удаляем объявление
    await RemoveAd(fake_uow).execute(ad_id)
    docs = fake_uow.search.snapshot()
    logger.info("After removal: %s", docs)
    assert ad_id not in docs

    # 4. Симулируем ситуацию, когда после удаления приходит событие "ad.updated"
    # и AdService возвращает snapshot с status="active" (например, если объявление было восстановлено)  # noqa: E501
    fake_ad_source.set(make_snapshot(ad_id=ad_id, title="test table", status="active"))

    # 5. Пытаемся повторно проиндексировать
    # Добавляем в кэш недавно удаленных, как это сделал бы Kafka consumer
    from src.application.usecases.index_ad import _recently_deleted_cache

    _recently_deleted_cache.add(ad_id)

    await index_ad.execute(ad_id)
    docs = fake_uow.search.snapshot()
    logger.info("After reindexing with active status: %s", docs)

    # 6. Проверяем поиск
    search_results, total = await Search(fake_uow).execute(
        query="test",
        category=None,
        city=None,
        min_price=None,
        max_price=None,
        sort=None,
        limit=20,
        offset=0,
    )
    logger.info("Search results: %s, total: %s", search_results, total)

    # Если статус активный, но объявление было недавно удалено, оно не должно быть проиндексировано повторно  # noqa: E501
    assert total == 0
    assert ad_id not in [doc.ad_id for doc in search_results]


@pytest.mark.asyncio
async def test_index_ad_after_remove_with_archived_status(
    fake_uow: FakeUnitOfWork,
    fake_ad_source: FakeAdSource,
) -> None:
    """Тест проверяет, что происходит, если после удаления приходит событие с архивным статусом"""  # noqa: E501
    ad_id = 48

    # 1. Создаем активное объявление
    fake_ad_source.set(make_snapshot(ad_id=ad_id, title="test chair", status="active"))

    # 2. Индексируем объявление
    await IndexAd(fake_uow, fake_ad_source).execute(ad_id)
    docs = fake_uow.search.snapshot()
    logger.info("After indexing: %s", docs)
    assert ad_id in docs

    # 3. Удаляем объявление
    await RemoveAd(fake_uow).execute(ad_id)
    docs = fake_uow.search.snapshot()
    logger.info("After removal: %s", docs)
    assert ad_id not in docs

    # 4. Симулируем ситуацию, когда после удаления приходит событие "ad.updated"
    # и AdService возвращает snapshot с status="archived"
    fake_ad_source.set(
        make_snapshot(ad_id=ad_id, title="test chair", status="archived")
    )

    # 5. Пытаемся повторно проиндексировать
    await IndexAd(fake_uow, fake_ad_source).execute(ad_id)
    docs = fake_uow.search.snapshot()
    logger.info("After reindexing with archived status: %s", docs)

    # 6. Проверяем поиск
    search_results, total = await Search(fake_uow).execute(
        query="chair",
        category=None,
        city=None,
        min_price=None,
        max_price=None,
        sort=None,
        limit=20,
        offset=0,
    )
    logger.info("Search results: %s, total: %s", search_results, total)

    # Если статус архивный, объявление должно быть удалено из индекса
    assert total == 0
    assert ad_id not in [doc.ad_id for doc in search_results]
