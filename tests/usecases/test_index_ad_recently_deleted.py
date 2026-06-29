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
async def test_index_ad_skips_recently_deleted(
    fake_uow: FakeUnitOfWork,
    fake_ad_source: FakeAdSource,
) -> None:
    """Тест проверяет, что IndexAd пропускает недавно удаленные объявления"""
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

    # 4. Пытаемся повторно проиндексировать с активным статусом
    # Но IndexAd должен пропустить, так как объявление было недавно удалено
    fake_ad_source.set(make_snapshot(ad_id=ad_id, title="test table", status="active"))

    # Добавляем в кэш недавно удаленных, как это сделал бы Kafka consumer
    from src.application.usecases.index_ad import _recently_deleted_cache

    _recently_deleted_cache.add(ad_id)

    await index_ad.execute(ad_id)
    docs = fake_uow.search.snapshot()
    logger.info("After reindexing attempt: %s", docs)

    # Объявление не должно быть проиндексировано повторно
    assert ad_id not in docs

    # 5. Проверяем поиск
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
    assert total == 0
    assert ad_id not in [doc.ad_id for doc in search_results]


@pytest.mark.asyncio
async def test_index_ad_allows_reindexing_after_cache_clear(
    fake_uow: FakeUnitOfWork,
    fake_ad_source: FakeAdSource,
) -> None:
    """Тест проверяет, что после очистки кэша можно повторно индексировать объявление"""
    ad_id = 48

    # 1. Создаем активное объявление
    fake_ad_source.set(make_snapshot(ad_id=ad_id, title="test chair", status="active"))

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

    # 4. Очищаем кэш недавно удаленных
    from src.application.usecases.index_ad import clear_recently_deleted_cache

    clear_recently_deleted_cache()

    # 5. Пытаемся повторно проиндексировать с активным статусом
    fake_ad_source.set(make_snapshot(ad_id=ad_id, title="test chair", status="active"))
    await index_ad.execute(ad_id)
    docs = fake_uow.search.snapshot()
    logger.info("After reindexing with cleared cache: %s", docs)

    # Объявление должно быть проиндексировано повторно
    assert ad_id in docs

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
    assert total == 1
    assert ad_id in [doc.ad_id for doc in search_results]
