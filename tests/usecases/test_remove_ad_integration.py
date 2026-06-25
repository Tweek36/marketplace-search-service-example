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
async def test_remove_ad_integration_flow(
    fake_uow: FakeUnitOfWork,
    fake_ad_source: FakeAdSource,
) -> None:
    """Тест воспроизводит поток: создание → индексация → удаление → поиск"""
    # 1. Создаем активное объявление
    ad_id = 47
    fake_ad_source.set(make_snapshot(ad_id=ad_id, title="test table", status="active"))

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

    # 4. Проверяем поиск - объявление не должно возвращаться
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
async def test_remove_ad_with_reindexing(
    fake_uow: FakeUnitOfWork,
    fake_ad_source: FakeAdSource,
) -> None:
    """Тест проверяет, что после удаления повторная индексация не восстанавливает объявление"""
    # 1. Создаем активное объявление
    ad_id = 48
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

    # 4. Пытаемся повторно проиндексировать (как будто пришло событие ad.updated)
    # Но AdSource.get() вернет None, так как объявление удалено
    fake_ad_source.remove(ad_id)
    await IndexAd(fake_uow, fake_ad_source).execute(ad_id)
    docs = fake_uow.search.snapshot()
    logger.info("After reindexing: %s", docs)
    assert ad_id not in docs

    # 5. Проверяем поиск
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
    assert total == 0
    assert ad_id not in [doc.ad_id for doc in search_results]