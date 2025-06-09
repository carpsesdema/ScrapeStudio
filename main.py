#!/usr/bin/env python3
"""
RAG Data Studio - Main Entry Point

Launch either the visual scraping GUI or the backend scraping interface.
"""

import sys
import os
import argparse
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def launch_visual_studio():
    """Launch the main RAG Data Studio visual interface"""
    try:
        # Adjusted import path to reflect new structure
        from rag_data_studio.main_application import QApplication, RAGDataStudio

        app = QApplication(sys.argv)
        app.setApplicationName("RAG Data Studio")
        app.setStyle("Fusion")

        window = RAGDataStudio()
        window.show()

        return app.exec()
    except ImportError as e:
        print(f"❌ Failed to import RAG Data Studio GUI: {e}")
        print("💡 Try installing missing dependencies: pip install PySide6")
        # Add traceback for easier debugging
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"❌ An unexpected error occurred while launching the GUI: {e}")
        import traceback
        traceback.print_exc()
        return 1


def run_scraper_cli(query_or_config):
    """Run the scraper from command line"""
    try:
        from scraper.searcher import run_professional_pipeline
        from utils.logger import setup_logger
        import config

        logger = setup_logger(name=config.APP_NAME, log_file=config.LOG_FILE_PATH)
        logger.info(f"Starting CLI scraper for: {query_or_config}")

        # The function now returns two values, we need to handle them
        enriched_items, metrics = run_professional_pipeline(
            query_or_config_path=query_or_config,
            logger_instance=logger
        )

        print(f"\n🎯 Scraping completed!")
        print(f"📊 Processed {len(enriched_items)} items")
        # You might want to get the actual export path from the config if possible
        # For now, pointing to the default directory
        print(f"📁 Data exported based on your config file settings.")

        if metrics and metrics.errors:
            print(f"\n⚠️ Encountered {len(metrics.errors)} errors during the run.")
            for error in metrics.errors[:5]: # Print first 5 errors
                print(f"   - {error}")

        return 0
    except Exception as e:
        print(f"❌ Scraping failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    parser = argparse.ArgumentParser(description="RAG Data Studio - Professional Scraping Platform")
    parser.add_argument("--mode", choices=["visual", "cli"], default="visual",
                        help="Launch mode: 'visual' (main GUI) or 'cli' (command line)")
    parser.add_argument("--query", type=str, help="Query or config file path for CLI mode")

    args = parser.parse_args()

    # Create necessary directories
    os.makedirs("logs", exist_ok=True)
    os.makedirs("data_exports", exist_ok=True)
    # The new project manager will handle its own directory creation

    print("🎯 RAG Data Studio")
    print("=" * 50)

    if args.mode == "visual":
        print("🚀 Launching Visual Scraping Studio...")
        return launch_visual_studio()
    elif args.mode == "cli":
        if not args.query:
            print("❌ CLI mode requires --query parameter (e.g., --query my_config.yaml)")
            return 1
        print(f"⚡ Running CLI scraper for: {args.query}")
        return run_scraper_cli(args.query)


if __name__ == "__main__":
    sys.exit(main())