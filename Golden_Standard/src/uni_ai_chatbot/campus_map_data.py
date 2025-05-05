from os import getenv
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(getenv("SUPABASE_URL"), getenv("SUPABASE_SERVICE_ROLE_KEY"))


def load_campus_map():
    """
    Load campus locations data from Supabase.
    Includes campus areas for each location.
    """
    response = supabase.table("campus_locations").select("name, type, campus_areas(name)").execute()
    return response.data