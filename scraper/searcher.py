# scraper/searcher.py
import logging
import json
from typing import List, Dict, Any, Tuple, Optional
from pydantic import HttpUrl

from .config_manager import ConfigManager
from .fetcher_pool import FetcherPool
from .content_router import ContentRouter
from .rag_models import StructuredDataItem, FetchedItem

logger = logging.getLogger(__name__)


def run_pipeline(config_path: str) -> Tuple[List[StructuredDataItem], Dict[str, Any]]:
    """The main URL-fetching scraping pipeline."""
    metrics = {'urls_fetched': 0, 'items_extracted': 0, 'errors': []}
    cfg_manager = ConfigManager(config_path)
    if not cfg_manager.config:
        metrics['errors'].append("Failed to load or parse configuration file.")
        return [], metrics

    logger.info(f"Pipeline started for project: {cfg_manager.config.domain_info.get('name', 'Untitled')}")

    fetcher = FetcherPool()
    router = ContentRouter()
    all_extracted_items = []

    try:
        for source in cfg_manager.config.sources:
            logger.info(f"Processing source: {source.name}")
            fetch_tasks = [(str(seed), source.source_type or source.name, source.name) for seed in source.seeds]
            fetched_items = fetcher.fetch_all(fetch_tasks)
            metrics['urls_fetched'] += len(fetched_items)

            for fetched_item in fetched_items:
                parsed_item = router.route_and_parse(fetched_item, source)
                if parsed_item and parsed_item.custom_fields:
                    final_item = StructuredDataItem(
                        id=parsed_item.id,
                        source_url=parsed_item.source_url,
                        source_type=parsed_item.source_type,
                        query_used=parsed_item.query_used,
                        title=parsed_item.title,
                        structured_data=parsed_item.custom_fields,
                        unstructured_text=parsed_item.main_text_content,
                        metadata={'parser_metadata': parsed_item.parser_metadata}
                    )
                    all_extracted_items.append(final_item)

        metrics['items_extracted'] = len(all_extracted_items)
    except Exception as e:
        logger.error(f"Critical pipeline error: {e}", exc_info=True)
        metrics['errors'].append(f"Critical error: {e}")
    finally:
        fetcher.shutdown()

    return all_extracted_items, metrics


def run_pipeline_on_html(config_path: str, html_content: str) -> Tuple[List[StructuredDataItem], Dict[str, Any]]:
    """
    NEW: A pipeline that scrapes directly from provided HTML content, bypassing the fetcher.
    """
    metrics = {'urls_fetched': 0, 'items_extracted': 0, 'errors': []}
    cfg_manager = ConfigManager(config_path)
    if not cfg_manager.config:
        metrics['errors'].append("Failed to load or parse configuration file.")
        return [], metrics

    logger.info(f"HTML content pipeline started for: {cfg_manager.config.domain_info.get('name', 'Untitled')}")

    router = ContentRouter()
    all_extracted_items = []

    # We'll run the rules from the FIRST source in the config against the provided HTML
    if not cfg_manager.config.sources:
        metrics['errors'].append("No sources defined in the configuration.")
        return [], metrics

    source = cfg_manager.config.sources[0]
    logger.info(f"Applying rules from source: {source.name}")

    # Create a dummy FetchedItem to pass to the router
    dummy_url = source.seeds[0] if source.seeds else HttpUrl("http://local.scrape")
    fetched_item = FetchedItem(
        source_url=dummy_url,
        content=html_content,
        source_type=source.source_type or source.name,
        query_used="direct_html_content"
    )

    parsed_item = router.route_and_parse(fetched_item, source)
    if parsed_item and parsed_item.custom_fields:
        final_item = StructuredDataItem(
            id=parsed_item.id,
            source_url=parsed_item.source_url,
            source_type=parsed_item.source_type,
            query_used=parsed_item.query_used,
            title=parsed_item.title,
            structured_data=parsed_item.custom_fields,
            unstructured_text=parsed_item.main_text_content,
            metadata={'parser_metadata': parsed_item.parser_metadata}
        )
        all_extracted_items.append(final_item)

    metrics['items_extracted'] = len(all_extracted_items)
    logger.info(f"HTML content pipeline finished. Extracted {metrics['items_extracted']} items.")
    return all_extracted_items, metrics


def save_results(items: List[StructuredDataItem], output_path: str, file_format: str):
    logger.info(f"Saving {len(items)} items to {output_path} in {file_format} format.")
    try:
        import os
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            if file_format == 'jsonl':
                for item in items:
                    f.write(item.model_dump_json() + '\n')
            elif file_format == 'json':
                json.dump([item.model_dump(mode='json') for item in items], f, indent=2)
            else:
                logger.error(f"Unsupported export format: {file_format}")
    except Exception as e:
        logger.error(f"Failed to save results to {output_path}: {e}")