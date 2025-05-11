import logging
import argparse
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def migrate_to_supabase():
    """
    Migrate from FAISS to Supabase pgvector.
    This script performs the following steps:
    1. Set up pgvector extension in Supabase
    2. Process documents and store embeddings in Supabase
    """
    # Load environment variables
    load_dotenv()
    
    try:
        # Step 1: Set up pgvector extension
        logger.info("Step 1: Setting up pgvector extension in Supabase...")
        from setup_pgvector import setup_pgvector
        setup_pgvector()
        logger.info("✓ pgvector extension setup complete")
        
        # Step 2: Process and store embeddings in Supabase
        logger.info("Step 2: Processing documents and storing embeddings in Supabase...")
        from preprocess_documents_supabase import process_and_save_to_supabase
        process_and_save_to_supabase()
        logger.info("✓ Embeddings stored in Supabase successfully")
        
        logger.info("Migration complete! Your bot is now using Supabase pgvector store.")
        logger.info("To use the new vector store:")
        logger.info("1. Replace imports from qa_service.py to qa_service_supabase.py")
        logger.info("2. Update your main.py to use the new QA service")
        
        return True
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate from FAISS to Supabase pgvector")
    args = parser.parse_args()
    
    if migrate_to_supabase():
        print("Migration completed successfully!")
    else:
        print("Migration failed. Please check the logs for details.")
        exit(1)