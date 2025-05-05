from os import getenv
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(getenv("SUPABASE_URL"), getenv("SUPABASE_SERVICE_ROLE_KEY"))


def load_locker_hours():
    """
    Load locker hours data from Supabase.
    Returns raw data that needs to be parsed.
    """
    response = supabase.table("locker_hours").select(
        "status, basement, colleges(name), days(name), time_ranges(label, start_time, end_time)"
    ).execute()
    return response.data