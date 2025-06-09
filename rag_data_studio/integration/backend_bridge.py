# rag_data_studio/integration/backend_bridge.py
"""
Integration bridge between the GUI and the scraping backend.
Runs tasks in a QThread to avoid freezing the GUI.
"""
import logging
from typing import List, Dict, Any, Optional

import requests
from bs4 import BeautifulSoup
from PySide6.QtCore import QObject, Signal, QThread


class BackendWorker(QObject):
    """A QObject worker that performs backend tasks in a separate thread."""
    test_results_ready = Signal(dict)
    scraping_finished = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, logger_instance=None):
        super().__init__()
        self.logger = logger_instance or logging.getLogger("BackendWorker")

    def test_selectors_on_url(self, url: str, selectors_config: List[Dict[str, Any]]):
        """Tests a list of selectors against a live URL."""
        results = {}
        if not url or not selectors_config:
            self.error_occurred.emit("URL or selector definitions cannot be empty.")
            return

        try:
            self.logger.info(f"Testing {len(selectors_config)} selectors on URL: {url}")
            response = requests.get(url, timeout=15, headers={'User-Agent': 'ScrapeStudio-SelectorTester/1.0'})
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            for sel_config in selectors_config:
                name = sel_config.get('name', 'Unnamed Rule')
                selector_str = sel_config.get('selector')
                extract_type = sel_config.get('extract_type', 'text')
                attribute_name = sel_config.get('attribute_name')

                if not selector_str:
                    results[name] = {'success': False, 'found_count': 0, 'sample_values': [], 'error': 'Selector is empty.'}
                    continue

                current_result = {'success': False, 'found_count': 0, 'sample_values': [], 'error': None}
                try:
                    elements = soup.select(selector_str)
                    current_result['found_count'] = len(elements)

                    if elements:
                        current_result['success'] = True
                        for elem in elements[:5]:  # Sample first 5
                            value = None
                            if extract_type == "text":
                                value = elem.get_text(strip=True)
                            elif extract_type == "attribute" and attribute_name:
                                value = elem.get(attribute_name, "")
                            elif extract_type == "html":
                                value = str(elem)
                            if value is not None:
                                value_str = str(value)
                                current_result['sample_values'].append(value_str[:200])
                    else:
                        current_result['error'] = "No elements found."

                except Exception as e_select:
                    self.logger.warning(f"Error testing selector '{name}' ({selector_str}): {e_select}")
                    current_result['error'] = str(e_select)
                results[name] = current_result

            self.test_results_ready.emit(results)

        except requests.exceptions.RequestException as e_req:
            self.logger.error(f"Request failed for URL {url}: {e_req}")
            self.error_occurred.emit(f"Failed to fetch URL: {e_req}")
        except Exception as e_general:
            self.logger.error(f"General error during selector testing for {url}: {e_general}", exc_info=True)
            self.error_occurred.emit(f"An unexpected error occurred: {e_general}")

    def run_scraping_pipeline(self, project_config_dict: Dict[str, Any]):
        """Runs the main scraping pipeline with a project config."""
        # This is a placeholder for running the full scraper.
        # It would involve formatting the config, calling run_professional_pipeline, etc.
        self.logger.info(f"Starting scraping pipeline for project: {project_config_dict.get('name')}")
        # ... implementation to come ...
        # For now, just emit a finished signal with dummy data.
        import time
        time.sleep(3) # Simulate work
        self.scraping_finished.emit([{"status": "complete", "message": "Pipeline run finished (simulated)."}])