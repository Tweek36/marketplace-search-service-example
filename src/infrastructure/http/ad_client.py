import logging
import urllib.parse

import httpx

from src.application.ports.ad_source import AdSnapshot, AdSource

logger = logging.getLogger(__name__)


class AdServiceAdSource(AdSource):
    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._base_url = base_url

    async def get(self, ad_id: int) -> AdSnapshot | None:
        url = urllib.parse.urljoin(self._base_url, f"internal/ads/{ad_id}")
        logger.info("Fetching ad %s from ad-service at %s", ad_id, url)
        try:
            resp = await self._client.get(url)
            logger.debug(
                "Received response for ad %s: %s - %s",
                ad_id,
                resp.status_code,
                resp.text,
            )
        except httpx.HTTPError as exc:
            logger.error("Failed to fetch ad %s: %s", ad_id, exc)
            return None

        if resp.status_code != 200:
            logger.warning(
                "Ad %s not found or error in response: %s - %s",
                ad_id,
                resp.status_code,
                resp.text,
            )
            return None

        try:
            data = resp.json()
            logger.debug("Parsed ad data for %s: %s", ad_id, data)
            return AdSnapshot(
                ad_id=data["id"],
                title=data["title"],
                description=data["description"],
                price=data["price"],
                category=data["category"],
                city=data["city"],
                status=data["status"],
            )
        except (KeyError, ValueError) as e:
            logger.error(
                "Failed to parse ad data for %s: %s. Response: %s", ad_id, e, resp.text
            )
            return None
