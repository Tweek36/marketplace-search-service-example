import logging

from src.application.ports.uow import UnitOfWork
from src.application.ports.usecases import RemoveAdPort


class RemoveAd(RemoveAdPort):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, ad_id: int) -> None:
        logger = logging.getLogger(__name__)
        logger.info("Removing ad %s from search index", ad_id)
        async with self._uow:
            await self._uow.search.delete(ad_id)
            await self._uow.commit()

        # Добавляем в кэш недавно удаленных для предотвращения повторной индексации
        # в случае получения события ad.updated после ad.deleted
        from src.application.usecases.index_ad import _recently_deleted_cache

        _recently_deleted_cache.add(ad_id)

        logger.info("Successfully removed ad %s from search index", ad_id)
