# scraper/searcher.py
import logging
import json
import uuid
from typing import List, Dict, Any, Tuple, Optional, Callable
from pydantic import HttpUrl

from .config_manager import ConfigManager
from .fetcher_pool import FetcherPool
from .content_router import ContentRouter
from .rag_models import StructuredDataItem, FetchedItem

logger = logging.getLogger(__name__)


def run_pipeline(config_path: str, progress_callback: Optional[Callable[[str, int], None]] = None) -> Tuple[
    List[StructuredDataItem], Dict[str, Any]]:
    """The main URL-fetching scraping pipeline with detailed progress."""
    metrics = {'urls_fetched': 0, 'items_extracted': 0, 'errors': []}

    def update_progress(msg, percent):
        logger.info(f"Pipeline progress: {msg} ({percent}%)")
        if progress_callback:
            try:
                progress_callback(msg, percent)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    try:
        update_progress("Loading configuration...", 5)
        cfg_manager = ConfigManager(config_path)
        if not cfg_manager.config:
            metrics['errors'].append("Failed to load or parse configuration file.")
            update_progress("Error: Bad config file", 100)
            return [], metrics

        logger.info(f"Pipeline started for project: {cfg_manager.config.domain_info.get('name', 'Untitled')}")

        fetcher = FetcherPool()
        router = ContentRouter()
        all_extracted_items = []

        try:
            sources = cfg_manager.config.sources
            total_sources = len(sources)

            for i, source in enumerate(sources):
                update_progress(f"Processing source {i + 1}/{total_sources}: {source.name}",
                                10 + (i * 60 // total_sources))

                # Create fetch tasks from seeds
                fetch_tasks = []
                for seed in source.seeds:
                    fetch_tasks.append((str(seed), source.source_type or source.name, source.name))

                if not fetch_tasks:
                    logger.warning(f"No seeds found for source {source.name}")
                    continue

                update_progress(f"Fetching {len(fetch_tasks)} URLs...", 25 + (i * 60 // total_sources))
                fetched_items = fetcher.fetch_all(fetch_tasks)
                metrics['urls_fetched'] += len(fetched_items)

                update_progress(f"Parsing {len(fetched_items)} pages...", 60 + (i * 30 // total_sources))

                for fetched_item in fetched_items:
                    try:
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
                    except Exception as e:
                        logger.error(f"Error processing item {fetched_item.source_url}: {e}")
                        metrics['errors'].append(f"Parse error for {fetched_item.source_url}: {e}")

        except Exception as e:
            logger.error(f"Error during fetching phase: {e}")
            metrics['errors'].append(f"Fetch error: {e}")
        finally:
            fetcher.shutdown()

        metrics['items_extracted'] = len(all_extracted_items)
        update_progress("Pipeline finished.", 95)

        logger.info(f"Pipeline completed: {metrics['items_extracted']} items extracted")
        return all_extracted_items, metrics

    except Exception as e:
        logger.error(f"Critical pipeline error: {e}", exc_info=True)
        metrics['errors'].append(f"Critical error: {e}")
        update_progress(f"Error: {e}", 100)
        return [], metrics


def run_pipeline_on_html(config_path: str, html_content: str,
                         progress_callback: Optional[Callable[[str, int], None]] = None) -> Tuple[
    List[StructuredDataItem], Dict[str, Any]]:
    """Pipeline that scrapes directly from provided HTML content with detailed progress."""
    metrics = {'urls_fetched': 1, 'items_extracted': 0, 'errors': []}

    def update_progress(msg, percent):
        logger.info(f"HTML Pipeline progress: {msg} ({percent}%)")
        if progress_callback:
            try:
                progress_callback(msg, percent)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    try:
        update_progress("Loading configuration...", 10)
        cfg_manager = ConfigManager(config_path)
        if not cfg_manager.config:
            error_msg = "Failed to load configuration."
            metrics['errors'].append(error_msg)
            update_progress("Error: Bad config file", 100)
            return [], metrics

        logger.info(f"✅ Config loaded for HTML processing")

        update_progress("Validating HTML content...", 20)

        if not html_content or len(html_content.strip()) < 100:
            error_msg = "HTML content is empty or too short."
            metrics['errors'].append(error_msg)
            update_progress("Error: No HTML content", 100)
            return [], metrics

        if not cfg_manager.config.sources:
            error_msg = "No sources defined in config."
            metrics['errors'].append(error_msg)
            update_progress("Error: No sources", 100)
            return [], metrics

        source = cfg_manager.config.sources[0]
        logger.info(f"✅ Using source: {source.name} with {len(source.selectors.custom_fields)} rules")

        update_progress("Creating HTML parser...", 40)

        # Create a valid dummy URL
        dummy_url = source.seeds[0] if source.seeds else HttpUrl("https://example.com/scraped-content")

        # Create a FetchedItem from the HTML content
        fetched_item = FetchedItem(
            id=str(uuid.uuid4()),
            source_url=dummy_url,
            content=html_content,
            source_type=source.source_type or source.name,
            query_used="direct_html_content",
            title="Browser Content"
        )

        update_progress("Parsing HTML with extraction rules...", 60)

        router = ContentRouter()
        all_extracted_items = []

        try:
            parsed_item = router.route_and_parse(fetched_item, source)

            if parsed_item:
                logger.info(f"✅ HTML parsed successfully")
                logger.info(f"   Title: {parsed_item.title}")
                logger.info(f"   Custom fields: {list(parsed_item.custom_fields.keys())}")

                if parsed_item.custom_fields:
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
                    logger.info(f"✅ Created structured item with data: {list(final_item.structured_data.keys())}")
                else:
                    logger.warning("❌ No custom fields extracted from HTML")
            else:
                logger.warning("❌ Failed to parse HTML content")

        except Exception as e:
            logger.error(f"Error during HTML parsing: {e}", exc_info=True)
            metrics['errors'].append(f"HTML parsing error: {e}")

        metrics['items_extracted'] = len(all_extracted_items)
        update_progress("HTML processing complete.", 95)

        logger.info(f"HTML pipeline completed: {metrics['items_extracted']} items extracted")
        return all_extracted_items, metrics

    except Exception as e:
        logger.error(f"Critical HTML pipeline error: {e}", exc_info=True)
        metrics['errors'].append(f"Critical error: {e}")
        update_progress(f"Error: {e}", 100)
        return [], metrics


def save_results(items: List[StructuredDataItem], output_path: str, file_format: str):
    """Save results to file."""
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

        logger.info(f"✅ Results saved successfully to {output_path}")
    except Exception as e:
        logger.error(f"Failed to save results to {output_path}: {e}")