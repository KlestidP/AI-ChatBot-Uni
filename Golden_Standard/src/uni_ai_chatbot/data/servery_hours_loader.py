from uni_ai_chatbot.utils.database import get_supabase_client


def load_servery_hours():
    """
    Load servery hours data from Supabase.
    Returns raw data that needs to be parsed.
    """
    supabase = get_supabase_client()
    response = supabase.table("servery_hours").select(
        "meal_type, colleges(name), days(name), time_ranges(label, start_time, end_time)"
    ).execute()
    return response.data
