"""
Тест симулирует реальный сценарий из описания проблемы:
1. Создается объявление с уникальным search_token
2. Оно индексируется
3. Удаляется
4. При поиске оно не должно возвращаться
"""

import logging

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.application.ports.ad_source import AdSnapshot
from src.application.usecases.index_ad import IndexAd
from src.application.usecases.remove_ad import RemoveAd
from src.application.usecases.search import Search
from src.infrastructure.http.ad_client import AdServiceAdSource
from src.infrastructure.persistence.models import Base
from src.infrastructure.persistence.repositories import SQLAlchemySearchRepository
from src.infrastructure.persistence.uow import SQLAlchemyUnitOfWork

# Настроим логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Тестовая база данных - используем SQLite в памяти для теста
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine):
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def search_repo(session):
    return SQLAlchemySearchRepository(session)


@pytest_asyncio.fixture
async def uow(search_repo):
    return SQLAlchemyUnitOfWork(search_repo)


@pytest_asyncio.fixture
async def ad_source():
    # Используем фейковый клиент для тестов
    class FakeAdClient:
        def __init__(self):
            self.snapshots = {
                47: AdSnapshot(
                    ad_id=47,
                    title="autotest1782388188589985486 table",
                    description="D",
                    price=300,
                    category="c",
                    city="M",
                    status="active",
                )
            }

        async def get(self, url):
            # Извлекаем ad_id из URL
            ad_id = int(url.split("/")[-1])
            if ad_id in self.snapshots:
                return httpx.Response(
                    200,
                    json={
                        "id": self.snapshots[ad_id].ad_id,
                        "title": self.snapshots[ad_id].title,
                        "description": self.snapshots[ad_id].description,
                        "price": self.snapshots[ad_id].price,
                        "category": self.snapshots[ad_id].category,
                        "city": self.snapshots[ad_id].city,
                        "status": self.snapshots[ad_id].status,
                    },
                )
            return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(app=FakeAdClient()))
    return AdServiceAdSource(client, "http://localhost:8002")


@pytest.mark.asyncio
async def test_real_scenario(uow, ad_source):
    """Тест воспроизводит реальный сценарий из описания проблемы"""
    ad_id = 47
    search_token = "autotest1782388188589985486"

    # 1. Индексируем объявление
    await IndexAd(uow, ad_source).execute(ad_id)

    # Проверяем, что объявление появилось в индексе
    search_results, total = await Search(uow).execute(
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
    await RemoveAd(uow).execute(ad_id)

    # Проверяем, что объявление удалено из индекса
    search_results, total = await Search(uow).execute(
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
    await IndexAd(uow, ad_source).execute(ad_id)

    # Проверяем, что объявление не появилось снова в индексе
    search_results, total = await Search(uow).execute(
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
