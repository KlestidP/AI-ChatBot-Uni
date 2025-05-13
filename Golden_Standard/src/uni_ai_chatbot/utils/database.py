from supabase import create_client, Client
from functools import lru_cache
from uni_ai_chatbot.configurations.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """
    Initialize and return a Supabase client (singleton pattern)

    Returns:
        A configured Supabase client

    Raises:
        ValueError: If credentials are not found
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("Supabase credentials not found in environment variables")

    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
