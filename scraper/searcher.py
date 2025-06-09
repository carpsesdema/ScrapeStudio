# scraper/searcher.py
import logging
import json
from typing import List, Dict, Any, Tuple

from .config_manager import ConfigManager
from .fetcher_pool import FetcherPool
from .content_router import ContentRouter
from .rag_models import StructuredDataItem

logger = logging.getLogger(__name__)


def run_pipeline(config_path: str) -> Tuple[List[StructuredDataItem], Dict[str, Any]]:
    """
    The main scraping pipeline.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        A tuple containing the list of structured data items and a metrics dictionary.
    """
    metrics = {
        'sources_processed': 0,
        'urls_fetched': 0,
        'items_extracted': 0,
        'errors': []
    }

    # 1. Load Configuration
    cfg_manager = ConfigManager(config_path)
    if not cfg_manager.config:
        metrics['errors'].append("Failed to load or parse configuration file.")
        return [], metrics

    logger.info(f"Pipeline started for project: {cfg_manager.config.domain_info.get('name', 'Untitled')}")

    fetcher = FetcherPool()
    router = ContentRouter()
    all_extracted_items = []

    try:
        # 2. Process each source defined in the config
        for source in cfg_manager.config.sources:
            logger.info(f"Processing source: {source.name}")
            metrics['sources_processed'] += 1

            # 3. Fetch all seed URLs for the source in parallel
            fetch_tasks = [(str(seed), source.source_type or source.name, source.name) for seed in source.seeds]
            fetched_items = fetcher.fetch_all(fetch_tasks)
            metrics['urls_fetched'] += len(fetched_items)

            # 4. Route and parse each fetched item
            for fetched_item in fetched_items:
                parsed_item = router.route_and_parse(fetched_item, source)

                if not parsed_item:
                    continue

                # 5. Transform ParsedItem into the final StructuredDataItem
                # Check if the main custom field (structured list) exists and has data
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

        metrics['items_extracted'] = len(all_extracted_items)
        logger.info(f"Pipeline finished. Extracted {metrics['items_extracted']} items.")

    except Exception as e:
        logger.error(f"Critical pipeline error: {e}", exc_info=True)
        metrics['errors'].append(f"Critical error: {e}")
    finally:
        fetcher.shutdown()

    return all_extracted_items, metrics


def save_results(items: List[StructuredDataItem], output_path: str, file_format: str):
    """Saves the extracted items to a file."""
    logger.info(f"Saving {len(items)} items to {output_path} in {file_format} format.")
    try:
        # Ensure directory exists
        import os
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            if file_format == 'jsonl':
                for item in items:
                    f.write(item.model_dump_json() + '\n')
            elif file_format == 'json':
                # For regular JSON, dump a list of dictionaries
                json.dump([item.model_dump(mode='json') for item in items], f, indent=2)
            else:
                logger.error(f"Unsupported export format: {file_format}")

    except Exception as e:
        logger.error(f"Failed to save results to {output_path}: {e}")


# Example of how to run this from a command line for testing
if __name__ == '__main__':
    import sys
    from utils.logger import setup_logger

    if len(sys.argv) < 2:
        print("Usage: python -m scraper.searcher <path_to_config.yaml>")
        sys.exit(1)

    config_file_path = sys.argv[1]
    setup_logger()

    extracted_data, run_metrics = run_pipeline(config_file_path)

    print("\n--- Pipeline Metrics ---")
    print(json.dumps(run_metrics, indent=2))

    if extracted_data:
        print(f"\nSuccessfully extracted {len(extracted_data)} items.")
        # For simplicity, we assume one source and one export path from the config.
        # A more robust CLI would parse the config to find the correct output path.
        cfg = ConfigManager(config_file_path)
        if cfg.config:
            output_path = cfg.config.sources[0].export.output_path
            file_format = cfg.config.sources[0].export.format
            save_results(extracted_data, output_path, file_format)
            print(f"Results saved to {output_path}")
    else:
        print("\nNo data was extracted.")