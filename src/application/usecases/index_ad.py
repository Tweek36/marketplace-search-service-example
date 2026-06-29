import logging
import os
import time
from typing import Dict

from src.application.ports.ad_source import AdSource
from src.application.ports.uow import UnitOfWork
from src.application.ports.usecases import IndexAdPort


class RecentlyDeletedCache:
    """Синглтон для управления кэшом недавно удаленных объявлений"""

    _instance = None
    _recently_deleted_ads: Dict[int, float] = {}
    # Время жизни записи в кэше (в секундах)
    # Для продакшена - 5 секунд, для тестов - 1 секунда
    # Уменьшено с 300 до 5 секунд для более быстрого восстановления после временных проблем  # noqa: E501
    _deleted_cache_ttl = int(float(os.getenv("DELETED_CACHE_TTL", "5")))

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def clear(self) -> None:
        """Очистка кэша недавно удаленных объявлений"""
        self._recently_deleted_ads.clear()

    def cleanup_old_entries(self) -> None:
        """Очистка устаревших записей из кэша"""
        current_time = time.time()
        # Удаляем записи старше TTL
        old_keys = [
            ad_id
            for ad_id, timestamp in self._recently_deleted_ads.items()
            if current_time - timestamp > self._deleted_cache_ttl
        ]
        for ad_id in old_keys:
            self._recently_deleted_ads.pop(ad_id, None)

    def is_recently_deleted(self, ad_id: int) -> bool:
        """Проверяет, было ли объявление недавно удалено"""
        self.cleanup_old_entries()
        return ad_id in self._recently_deleted_ads

    def add(self, ad_id: int) -> None:
        """Добавляет объявление в кэш недавно удаленных"""
        self._recently_deleted_ads[ad_id] = time.time()


# Глобальный синглтон для кэша
_recently_deleted_cache = RecentlyDeletedCache()


def clear_recently_deleted_cache() -> None:
    """Очистка кэша недавно удаленных объявлений"""
    _recently_deleted_cache.clear()


class IndexAd(IndexAdPort):
    def __init__(self, uow: UnitOfWork, ad_source: AdSource) -> None:
        self._uow = uow
        self._ad_source = ad_source
        # Время жизни записи в кэше (в секундах)
        self._deleted_cache_ttl = 300  # 5 минут

    async def execute(self, ad_id: int) -> None:
        logger = logging.getLogger(__name__)
        logger.info("Indexing ad %s", ad_id)

        # Проверяем, было ли объявление недавно удалено
        if _recently_deleted_cache.is_recently_deleted(ad_id):
            logger.info("Ad %s was recently deleted, skipping indexing", ad_id)
            return

        snapshot = await self._ad_source.get(ad_id)
        async with self._uow:
            if snapshot is None or snapshot.status != "active":
                logger.info(
                    "Deleting ad %s from index (status: %s)",
                    ad_id,
                    snapshot.status if snapshot else "None",
                )
                await self._uow.search.delete(ad_id)
                # Добавляем в кэш недавно удаленных
                _recently_deleted_cache.add(ad_id)
            else:
                logger.info(
                    "Upserting ad %s to index (status: %s)", ad_id, snapshot.status
                )
                await self._uow.search.upsert(
                    ad_id=snapshot.ad_id,
                    title=snapshot.title,
                    description=snapshot.description,
                    price=snapshot.price,
                    category=snapshot.category,
                    city=snapshot.city,
                )
            await self._uow.commit()
        logger.info("Finished indexing ad %s", ad_id)
