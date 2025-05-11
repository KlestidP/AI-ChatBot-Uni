import os
import logging
from dotenv import load_dotenv
from supabase import create_client, Client

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get Supabase credentials
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


def get_supabase_client() -> Client:
    """Initialize and return a Supabase client"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Supabase credentials not found in environment variables")

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def setup_pgvector():
    """Set up the pgvector extension and create necessary tables in Supabase"""
    supabase = get_supabase_client()
    
    try:
        # Enable the pgvector extension
        logger.info("Enabling pgvector extension...")
        # This requires admin privileges in Supabase
        response = supabase.postgrest.rpc('enable_pgvector').execute()
        
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
    try:
        logger.info("Creating documents table if it doesn't exist...")
        # SQL query to create table with vector column
        create_table_query = """
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            content TEXT NOT NULL,
            metadata JSONB,
            embedding VECTOR(1536)
        );
        """
        
        # Execute the SQL query
        supabase.query(create_table_query).execute()
        logger.info("Documents table is ready")
        
    except Exception as e:
        logger.error(f"Error creating documents table: {e}")
        raise
    
    return True


if __name__ == "__main__":
    try:
        if setup_pgvector():
            logger.info("Successfully set up pgvector in Supabase")
    except Exception as e:
        logger.error(f"Error setting up pgvector: {e}")
        raise