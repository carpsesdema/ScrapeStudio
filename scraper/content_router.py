# scraper/content_router.py
import logging
from bs4 import BeautifulSoup, Tag
import trafilatura
import uuid
from typing import Optional, List, Dict, Any, Union

from .config_manager import SourceConfig, CustomFieldConfig
from .rag_models import FetchedItem, ParsedItem, ExtractedLinkInfo
from .parser import extract_relevant_links

logger = logging.getLogger(__name__)


class ContentRouter:
    def __init__(self):
        logger.info("ContentRouter initialized.")

    def _extract_single_field(self, context: Union[BeautifulSoup, Tag], config: CustomFieldConfig) -> Optional[Any]:
        elements = context.select(config.selector)
        if not elements:
            return None if not config.is_list else []

        values = []
        for elem in elements:
            value = None
            if config.extract_type == "text":
                value = elem.get_text(strip=True)
            elif config.extract_type == "attribute" and config.attribute_name:
                value = elem.get(config.attribute_name)
            elif config.extract_type == "html":
                value = str(elem)

            if value is not None:
                values.append(value)

        if not values:
            return None if not config.is_list else []

        return values if config.is_list else values[0]

    def _extract_custom_fields(self, soup: BeautifulSoup, config: SourceConfig) -> Dict[str, Any]:
        custom_data = {}
        if not config.selectors or not config.selectors.custom_fields:
            return custom_data

        for field_config in config.selectors.custom_fields:
            if field_config.extract_type == "structured_list":
                container_elements = soup.select(field_config.selector)
                structured_list = []
                for container in container_elements:
                    item_data = {}
                    for sub_field_config in field_config.sub_selectors:
                        item_data[sub_field_config.name] = self._extract_single_field(container, sub_field_config)
                    structured_list.append(item_data)
                custom_data[field_config.name] = structured_list
            else:
                custom_data[field_config.name] = self._extract_single_field(soup, field_config)

        return custom_data

    def route_and_parse(self, item: FetchedItem, config: SourceConfig) -> Optional[ParsedItem]:
        logger.info(f"Routing content for {item.source_url}")

        if not item.content:
            logger.warning(f"No content to parse for {item.source_url}")
            return None

        soup = BeautifulSoup(item.content, 'lxml')

        # Extract title
        title = item.title
        if not title:
            title_selector = config.selectors.title or 'title'
            title_tag = soup.select_one(title_selector)
            if title_tag:
                title = title_tag.get_text(strip=True)

        # Extract main text content (optional)
        main_text = None
        if config.selectors.main_content:
            content_tag = soup.select_one(config.selectors.main_content)
            if content_tag:
                main_text = content_tag.get_text(strip=True)
        if not main_text:
            main_text = trafilatura.extract(item.content, include_comments=False, include_tables=True)

        # Extract custom structured data
        custom_fields = self._extract_custom_fields(soup, config)

        # Extract links if needed
        links = extract_relevant_links(soup, str(item.source_url))

        return ParsedItem(
            id=str(uuid.uuid4()),
            fetched_item_id=item.id,
            source_url=item.source_url,
            source_type=item.source_type,
            query_used=item.query_used,
            title=title,
            main_text_content=main_text,
            custom_fields=custom_fields,
            extracted_links=links,
            parser_metadata={'parser': 'ContentRouterV2'}
        )