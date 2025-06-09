# scraper/parser.py
"""
Helper functions for parsing specific parts of HTML content.
"""
import logging
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from typing import List

from .rag_models import ExtractedLinkInfo
from pydantic import HttpUrl

logger = logging.getLogger(__name__)


def extract_relevant_links(soup: BeautifulSoup, base_url: str) -> List[ExtractedLinkInfo]:
    """
    Extracts and normalizes links from a BeautifulSoup object.
    Filters out mailto, tel, and anchor links.
    """
    extracted_links_info: List[ExtractedLinkInfo] = []

    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        if not href or href.startswith(('#', 'mailto:', 'tel:')):
            continue

        try:
            full_url_str = urljoin(base_url, href)
            # Use Pydantic for validation
            valid_http_url = HttpUrl(full_url_str)

            anchor_text = a_tag.get_text(strip=True)
            rel = a_tag.get('rel')

            link_info = ExtractedLinkInfo(
                url=valid_http_url,
                text=anchor_text if anchor_text else None,
                rel=" ".join(rel) if rel else None
            )
            extracted_links_info.append(link_info)

        except (ValueError, Exception) as e:
            # Pydantic's HttpUrl will raise a ValueError on invalid URLs
            logger.debug(f"Skipping invalid or non-http link '{href}': {e}")
            continue

    return extracted_links_info