# scraper/fetcher_pool.py
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List
import requests

import config
from .rag_models import FetchedItem

logger = logging.getLogger(__name__)


class FetcherPool:
    def __init__(self, num_workers: int = config.MAX_CONCURRENT_FETCHERS):
        self.num_workers = num_workers
        self.executor = ThreadPoolExecutor(max_workers=self.num_workers)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.USER_AGENT})

    def fetch_url(self, url: str, source_type: str, query_used: str) -> Optional[FetchedItem]:
        logger.info(f"Fetching URL: {url}")
        try:
            response = self.session.get(url, timeout=config.DEFAULT_REQUEST_TIMEOUT, allow_redirects=True)
            response.raise_for_status()

            encoding = response.encoding or response.apparent_encoding

            return FetchedItem(
                source_url=url,
                content=response.text,
                content_bytes=response.content,
                content_type_detected=response.headers.get('Content-Type', '').lower(),
                source_type=source_type,
                query_used=query_used,
                encoding=encoding
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    def fetch_all(self, tasks: List[tuple]) -> List[FetchedItem]:
        """
        Fetches a list of URLs in parallel.
        Args:
            tasks: A list of tuples, where each tuple is (url, source_type, query_used).
        """
        futures = {self.executor.submit(self.fetch_url, url, st, qu): url for url, st, qu in tasks}
        results = []

        for future in as_completed(futures):
            url = futures[future]
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Exception for URL {url} in future: {e}")

        return results

    def shutdown(self):
        self.executor.shutdown(wait=True)