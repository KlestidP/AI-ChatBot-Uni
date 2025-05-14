import logging
import sys
import time

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def check_and_initialize_database():
    """Check if database is initialized and set up required components if needed"""
    from uni_ai_chatbot.utils.database import get_supabase_client

    try:
        # Check if the documents table exists and has content
        supabase = get_supabase_client()

        # Check if table exists and has data
        logger.info("Checking if database is already initialized...")
        try:
            # First check if table exists by attempting to select a single row
            response = supabase.table("documents").select("id").limit(1).execute()

            # If we got here without an error, the table exists
            if response and hasattr(response, 'data') and len(response.data) > 0:
                logger.info(f"Database is already initialized with document embeddings.")
                return True
            else:
                logger.info("Documents table exists but may be empty. Proceeding with initialization...")
        except Exception as e:
            # If there's an error, the table might not exist
            logger.info(f"Checking database status: {str(e)}")
            logger.info("Documents table might not exist. Proceeding with initialization...")

        # Set up pgvector extension and table structure
        logger.info("Setting up database schema...")
        from uni_ai_chatbot.scripts.setup_pgvector import setup_pgvector
        setup_pgvector()

        # Then process and save embeddings
        logger.info("Processing data and creating embeddings...")
        try:
            from uni_ai_chatbot.scripts.preprocess_supabase import process_and_save_to_supabase
            process_and_save_to_supabase()
            logger.info("Successfully created and saved embeddings!")
        except Exception as embed_error:
            logger.error(f"Error creating embeddings: {embed_error}")
            logger.info("You may need to run embeddings creation manually after fixing the issue.")
            logger.info("Run: python -m uni_ai_chatbot.data.preprocess_supabase")
            # Continue with bot startup anyway

        return True

    except Exception as e:
        logger.error(f"Error checking or initializing database: {e}")
        # Continue anyway - we don't want to prevent bot from starting
        return False


if __name__ == "__main__":
    # Add a small delay to ensure database is ready
    time.sleep(5)

    success = check_and_initialize_database()
    sys.exit(0 if success else 1)