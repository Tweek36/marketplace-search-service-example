import logging
import typing

from aiokafka import AIOKafkaConsumer

from src.application.ports.usecases import IndexAdPort, RemoveAdPort

logger = logging.getLogger(__name__)


class KafkaAdsConsumer:
    def __init__(
        self,
        consumer: AIOKafkaConsumer,
        index_ad: IndexAdPort,
        remove_ad: RemoveAdPort,
    ) -> None:
        self._consumer = consumer
        self._index_ad = index_ad
        self._remove_ad = remove_ad

    async def run(self) -> None:
        async for msg in self._consumer:
            logger.info("Received message: %s", msg.value)
            try:
                await self._handle(msg.value)
                logger.info(
                    "Successfully handled message for ad_id: %s",
                    msg.value.get("payload", {}).get("ad_id"),
                )
            except Exception:
                logger.exception("failed to handle message %s", msg)
                continue
            await self._consumer.commit()

    async def _handle(self, value: dict[str, typing.Any]) -> None:
        event = value.get("event")
        payload = value.get("payload") or {}
        ad_id = payload.get("ad_id")
        logger.info("Handling event %s for ad_id %s", event, ad_id)

        if not isinstance(ad_id, int):
            logger.warning("skip message without ad_id: %s", value)
            return

        if event in ("ad.created", "ad.updated"):
            logger.info("Indexing ad with id %s", ad_id)
            await self._index_ad.execute(ad_id)
        elif event == "ad.deleted":
            logger.info("Removing ad with id %s", ad_id)
            await self._remove_ad.execute(ad_id)
        else:
            logger.warning("unknown event type: %s", event)
