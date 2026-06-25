import logging
import time
from typing import Dict

from src.application.ports.ad_source import AdSource
from src.application.ports.uow import UnitOfWork
from src.application.ports.usecases import IndexAdPort

# Глобальный кэш для отслеживания недавно удаленных объявлений
# Ключ: ad_id, значение: timestamp
_recently_deleted_ads: Dict[int, float] = {}


def clear_recently_deleted_cache() -> None:
    """Очистка кэша недавно удаленных объявлений"""
    global _recently_deleted_ads
    _recently_deleted_ads.clear()


def _cleanup_old_entries() -> None:
    """Очистка устаревших записей из кэша"""
    global _recently_deleted_ads
    current_time = time.time()
    # Удаляем записи старше TTL
    old_keys = [
        ad_id
        for ad_id, timestamp in _recently_deleted_ads.items()
        if current_time - timestamp > 300  # 5 минут
    ]
    for ad_id in old_keys:
        _recently_deleted_ads.pop(ad_id, None)


class IndexAd(IndexAdPort):
    def __init__(self, uow: UnitOfWork, ad_source: AdSource) -> None:
        self._uow = uow
        self._ad_source = ad_source
        # Время жизни записи в кэше (в секундах)
        self._deleted_cache_ttl = 300  # 5 минут

    def _cleanup_recently_deleted(self) -> None:
        """Очистка устаревших записей из кэша недавно удаленных объявлений"""
        _cleanup_old_entries()

    async def execute(self, ad_id: int) -> None:
        logger = logging.getLogger(__name__)
        logger.info("Indexing ad %s", ad_id)

        # Очистка кэша
        self._cleanup_recently_deleted()

        # Проверяем, было ли объявление недавно удалено
        _cleanup_old_entries()
        if ad_id in _recently_deleted_ads:
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
                _recently_deleted_ads[ad_id] = time.time()
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
