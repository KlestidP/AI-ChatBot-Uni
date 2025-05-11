import os
import logging
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Update the FAISS index for university chatbot")
    parser.add_argument("--force", action="store_true", help="Force update even if index exists")
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Import here to avoid errors if the script is run outside of project context
    from preprocess_documents import get_index_path, process_and_save_index

    index_path = get_index_path()
    index_exists = Path(index_path).exists()

    if index_exists and not args.force:
        logger.info(f"FAISS index already exists at {index_path}")
        logger.info("Use --force to rebuild the index")
        return

    logger.info("Updating FAISS index...")
    try:
        process_and_save_index()
        logger.info("FAISS index updated successfully")
    except Exception as e:
        logger.error(f"Error updating FAISS index: {e}")
        raise


if __name__ == "__main__":
    main()
