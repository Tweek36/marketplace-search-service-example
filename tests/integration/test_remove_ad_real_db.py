import asyncio
import logging
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.application.ports.ad_source import AdSnapshot
from src.application.usecases.index_ad import IndexAd
from src.application.usecases.remove_ad import RemoveAd
from src.application.usecases.search import Search
from src.infrastructure.http.ad_client import AdServiceAdSource
from src.infrastructure.persistence.models import Base, SearchIndexModel
from src.infrastructure.persistence.repositories import SQLAlchemySearchRepository
from src.infrastructure.persistence.uow import SQLAlchemyUnitOfWork
import httpx

# Настроим логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Тестовая база данных
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5435/search_db"

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
        async def get(self, url):
            # Симулируем ответ от Ad Service
            if "47" in url:  # Для ad_id=47
                return httpx.Response(200, json={
                    "id": 47,
                    "title": "test table",
                    "description": "D",
                    "price": 300,
                    "category": "c",
                    "city": "M",
                    "status": "active"
                })
            return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(app=FakeAdClient()))
    return AdServiceAdSource(client, "http://localhost:8002")

@pytest.mark.asyncio
async def test_remove_ad_real_db(uow, ad_source):
    """Интеграционный тест с реальной базой данных"""
    ad_id = 47

    # 1. Индексируем объявление
    await IndexAd(uow, ad_source).execute(ad_id)

    # Проверяем, что объявление появилось в индексе
    async with uow:
        repo = uow.search
        docs, total = await repo.search(query="test", category=None, city=None,
                                      min_price=None, max_price=None, sort=None,
                                      limit=20, offset=0)
        logger.info("After indexing - found %s documents: %s", total, docs)
        assert total > 0
        assert any(doc.ad_id == ad_id for doc in docs)

    # 2. Удаляем объявление
    await RemoveAd(uow).execute(ad_id)

    # Проверяем, что объявление удалено из индекса
    async with uow:
        repo = uow.search
        docs, total = await repo.search(query="test", category=None, city=None,
                                      min_price=None, max_price=None, sort=None,
                                      limit=20, offset=0)
        logger.info("After removal - found %s documents: %s", total, docs)
        assert total == 0, f"Expected 0 documents, but found {total}"
        assert not any(doc.ad_id == ad_id for doc in docs)

    # 3. Проверяем через Search usecase
    search_results, total = await Search(uow).execute(
        query="test",
        category=None,
        city=None,
        min_price=None,
        max_price=None,
        sort=None,
        limit=20,
        offset=0,
    )
    logger.info("Search usecase results: %s, total: %s", search_results, total)
    assert total == 0, f"Expected 0 search results, but found {total}"
    assert not any(doc.ad_id == ad_id for doc in search_results)