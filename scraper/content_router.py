# scraper/content_router.py
import logging
from bs4 import BeautifulSoup, Tag
import trafilatura
import uuid
from typing import Optional, List, Dict, Any, Union
import json

from .config_manager import SourceConfig, CustomFieldConfig
from .rag_models import FetchedItem, ParsedItem, ExtractedLinkInfo
from .parser import extract_relevant_links

logger = logging.getLogger(__name__)


class ContentRouter:
    def __init__(self):
        logger.info("ContentRouter initialized.")

    def _extract_single_field(self, context: Union[BeautifulSoup, Tag], config: CustomFieldConfig) -> Optional[Any]:
        try:
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

                if value is not None and value != "":
                    values.append(value)

            if not values:
                return None if not config.is_list else []

            return values if config.is_list else values[0]
        except Exception as e:
            logger.error(f"Error extracting field '{config.name}': {e}")
            return None

    def _extract_custom_fields(self, soup: BeautifulSoup, config: SourceConfig) -> Dict[str, Any]:
        custom_data = {}
        if not config.selectors or not config.selectors.custom_fields:
            return custom_data

        logger.info(f"🔍 Processing {len(config.selectors.custom_fields)} custom fields...")

        for field_config in config.selectors.custom_fields:
            field_name = field_config.name
            logger.info(f"📋 Processing field: {field_name} (type: {field_config.extract_type})")

            if field_config.extract_type == "structured_list":
                logger.info(f"🗂️ Processing structured list for '{field_name}'")
                logger.info(f"   Container selector: {field_config.selector}")
                logger.info(f"   Sub-selectors: {len(field_config.sub_selectors)}")

                container_elements = soup.select(field_config.selector)
                logger.info(f"   Found {len(container_elements)} container elements")

                if not container_elements:
                    logger.warning(f"   No container elements found for selector: {field_config.selector}")
                    custom_data[field_name] = []
                    continue

                structured_list = []
                for i, container in enumerate(container_elements):
                    item_data = {}
                    for sub_field_config in field_config.sub_selectors:
                        sub_field_name = sub_field_config.name
                        sub_value = self._extract_single_field(container, sub_field_config)
                        item_data[sub_field_name] = sub_value

                    non_empty_fields = sum(1 for v in item_data.values() if v is not None and v != "")
                    if non_empty_fields > 0:
                        structured_list.append(item_data)
                    else:
                        logger.warning(f"   Row {i + 1} has no data, skipping")

                custom_data[field_name] = structured_list

                ############################################################################
                # DEBUG CHECKPOINT 2: What data did the scraper actually extract?
                print("\n" + "#" * 50)
                print("DEBUG: CHECKPOINT 2 (content_router.py)")
                print(f"Extraction for '{field_name}' complete.")
                print(f"Found {len(structured_list)} items.")
                if structured_list:
                    print("First 3 items extracted by scraper:")
                    # Pretty print the first few items
                    for item in structured_list[:3]:
                        print(json.dumps(item, indent=2))
                else:
                    print("Structured list is EMPTY.")
                print("#" * 50 + "\n")
                ############################################################################

            else:
                value = self._extract_single_field(soup, field_config)
                custom_data[field_name] = value
                logger.info(f"✅ Field '{field_name}': {type(value)} = {str(value)[:100] if value else 'None'}")

        logger.info(f"🎯 Total custom data fields created: {list(custom_data.keys())}")
        return custom_data

    def route_and_parse(self, item: FetchedItem, config: SourceConfig) -> Optional[ParsedItem]:
        logger.info(f"🚀 Routing content for {item.source_url}")

        if not item.content:
            logger.warning(f"❌ No content to parse for {item.source_url}")
            return None

        soup = BeautifulSoup(item.content, 'lxml')
        logger.info(f"📄 Parsed HTML content ({len(item.content)} chars)")

        title = item.title
        if not title:
            title_selector = config.selectors.title or 'title'
            title_tag = soup.select_one(title_selector)
            if title_tag:
                title = title_tag.get_text(strip=True)

        main_text = None
        if config.selectors.main_content:
            content_tag = soup.select_one(config.selectors.main_content)
            if content_tag:
                main_text = content_tag.get_text(strip=True)
        if not main_text:
            main_text = trafilatura.extract(item.content, include_comments=False, include_tables=True)

        logger.info("🔧 Starting custom field extraction...")
        custom_fields = self._extract_custom_fields(soup, config)
        logger.info(f"✅ Custom field extraction complete. Fields: {list(custom_fields.keys())}")

        links = extract_relevant_links(soup, str(item.source_url))

        parsed_item = ParsedItem(
            id=str(uuid.uuid4()),
            fetched_item_id=item.id,
            source_url=item.source_url,
            source_type=item.source_type,
            query_used=item.query_used,
            title=title,
            main_text_content=main_text,
            custom_fields=custom_fields,
            extracted_links=links,
            parser_metadata={'parser': 'ContentRouterV3'}
        )

        logger.info(f"🎉 Created ParsedItem with {len(custom_fields)} custom fields")
        return parsed_item