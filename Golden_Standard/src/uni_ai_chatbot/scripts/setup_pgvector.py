import logging
from uni_ai_chatbot.utils.database import get_supabase_client

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def setup_pgvector():
    """Set up the pgvector extension and create necessary tables in Supabase"""
    supabase = get_supabase_client()

    try:
        # Enable the pgvector extension
        logger.info("Enabling pgvector extension...")
        # This requires admin privileges in Supabase
        try:
            # Updated RPC call with empty params
            response = supabase.postgrest.rpc('enable_pgvector', {}).execute()

            if hasattr(response, 'error') and response.error:
                if "extension already exists" in str(response.error):
                    logger.info("pgvector extension already enabled")
                else:
                    logger.error(f"Error enabling pgvector extension: {response.error}")
                    logger.info("You may need to enable the pgvector extension manually in the Supabase SQL editor")
                    logger.info("Run: CREATE EXTENSION IF NOT EXISTS vector;")
        except Exception as e:
            logger.warning(f"Could not enable pgvector via API: {e}")
            logger.info("You may need to enable the pgvector extension manually in the Supabase SQL editor")
            logger.info("Run: CREATE EXTENSION IF NOT EXISTS vector;")

        # Check if the documents table exists
        logger.info("Creating documents table if it doesn't exist...")

        # Use SQL through postgrest instead of direct query
        create_table_query = """
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            content TEXT NOT NULL,
            metadata JSONB,
            embedding VECTOR(1024)
        );
        """

        # Execute the SQL query by running an RPC function that executes SQL
        # First check if your Supabase instance has an execute_sql RPC function
        try:
            # Try to execute SQL directly
            supabase.postgrest.rpc('execute_sql', {'sql': create_table_query}).execute()
            logger.info("Documents table is ready")
        except Exception as e:
            logger.warning(f"Could not execute SQL via RPC: {e}")
            logger.info("Trying to create table via REST API...")

            # Alternative: Check if table exists and create it if it doesn't
            try:
                # Check if table exists by attempting to select
                supabase.table("documents").select("id").limit(1).execute()
                logger.info("Documents table already exists")
            except Exception as table_error:
                logger.warning(f"Error checking table: {table_error}")
                logger.info("You need to create the documents table manually in the Supabase SQL editor")
                logger.info(f"Run: {create_table_query}")
                # Don't raise an error since we'll assume the table was created manually

        return True

    except Exception as e:
        logger.error(f"Error setting up pgvector: {e}")
        raise


if __name__ == "__main__":
    try:
        if setup_pgvector():
            logger.info("Successfully set up pgvector in Supabase")
    except Exception as e:
        logger.error(f"Error setting up pgvector: {e}")
        raise