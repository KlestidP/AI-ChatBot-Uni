import logging
import argparse
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Update the vector embeddings in Supabase for university chatbot")
    parser.add_argument("--force", action="store_true", help="Force update all embeddings")
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Import here to avoid errors if the script is run outside of project context
    from setup_pgvector import setup_pgvector
    from preprocess_documents_supabase import process_and_save_to_supabase

    logger.info("Setting up pgvector extension if needed...")
    try:
        setup_pgvector()
    except Exception as e:
        logger.error(f"Error setting up pgvector: {e}")
        return

    logger.info("Updating vector embeddings in Supabase...")
    try:
        process_and_save_to_supabase()
        logger.info("Vector embeddings updated successfully")
    except Exception as e:
        logger.error(f"Error updating vector embeddings: {e}")
        raise


if __name__ == "__main__":
    main()