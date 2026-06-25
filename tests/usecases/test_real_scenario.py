"""
Тест симулирует реальный сценарий из описания проблемы:
1. Создается объявление с уникальным search_token
2. Оно индексируется
3. Удаляется
4. При поиске оно не должно возвращаться
"""

import logging

import pytest

from src.application.usecases.index_ad import IndexAd
from src.application.usecases.remove_ad import RemoveAd
from src.application.usecases.search import Search
from tests.conftest import FakeAdSource, FakeUnitOfWork, make_snapshot

# Настроим логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_real_scenario(
    fake_uow: FakeUnitOfWork,
    fake_ad_source: FakeAdSource,
) -> None:
    """Тест воспроизводит реальный сценарий из описания проблемы"""
    ad_id = 47
    search_token = "autotest1782388188589985486"

    # Настраиваем AdSource - возвращаем объявление с уникальным search_token
    fake_ad_source.set(
        make_snapshot(
            ad_id=ad_id,
            title=f"{search_token} table",
            description="D",
            price=300,
            category="c",
            city="M",
            status="active",
        )
    )

    # 1. Индексируем объявление
    await IndexAd(fake_uow, fake_ad_source).execute(ad_id)

    # Проверяем, что объявление появилось в индексе
    search_results, total = await Search(fake_uow).execute(
        query=search_token,
        category=None,
        city=None,
        min_price=None,
        max_price=None,
        sort=None,
        limit=20,
        offset=0,
    )
    logger.info("After indexing - search results: %s, total: %s", search_results, total)
    assert total == 1
    assert ad_id in [doc.ad_id for doc in search_results]

    # 2. Удаляем объявление
    await RemoveAd(fake_uow).execute(ad_id)

    # Проверяем, что объявление удалено из индекса
    search_results, total = await Search(fake_uow).execute(
        query=search_token,
        category=None,
        city=None,
        min_price=None,
        max_price=None,
        sort=None,
        limit=20,
        offset=0,
    )
    logger.info("After removal - search results: %s, total: %s", search_results, total)

    # Ожидаем, что объявление не будет найдено
    assert total == 0, f"Expected 0 search results, but found {total}"
    assert ad_id not in [doc.ad_id for doc in search_results]

    # 3. Симулируем ситуацию, когда после удаления приходит событие "ad.updated"
    # и AdService возвращает snapshot с status="active" (как в реальной проблеме)
    # Но наше исправление должно предотвратить повторную индексацию
    await IndexAd(fake_uow, fake_ad_source).execute(ad_id)

    # Проверяем, что объявление не появилось снова в индексе
    search_results, total = await Search(fake_uow).execute(
        query=search_token,
        category=None,
        city=None,
        min_price=None,
        max_price=None,
        sort=None,
        limit=20,
        offset=0,
    )
    logger.info(
        "After reindexing attempt - search results: %s, total: %s",
        search_results,
        total,
    )

    # Объявление не должно быть проиндексировано повторно
    assert total == 0, f"Expected 0 search results after reindexing, but found {total}"
    assert ad_id not in [doc.ad_id for doc in search_results]
