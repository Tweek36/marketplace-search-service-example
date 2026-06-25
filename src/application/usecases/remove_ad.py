import logging
import time

from src.application.ports.uow import UnitOfWork
from src.application.ports.usecases import RemoveAdPort
from src.application.usecases.index_ad import _recently_deleted_ads

class RemoveAd(RemoveAdPort):
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, ad_id: int) -> None:
        logger = logging.getLogger(__name__)
        logger.info("Removing ad %s from search index", ad_id)
        async with self._uow:
            await self._uow.search.delete(ad_id)
            await self._uow.commit()
        logger.info("Successfully removed ad %s from search index", ad_id)
        # Добавляем в кэш недавно удаленных
        _recently_deleted_ads[ad_id] = time.time()
