from os import getenv
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(getenv("SUPABASE_URL"), getenv("SUPABASE_SERVICE_ROLE_KEY"))


def load_faq_answers():
    """
    Load FAQ responses from Supabase.
    Returns a dictionary of questions and answers.
    """
    response = supabase.table("faq_responses").select("question, answer").execute()
    return {item["question"]: item["answer"] for item in response.data}