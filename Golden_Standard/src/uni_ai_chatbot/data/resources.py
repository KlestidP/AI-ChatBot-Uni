from uni_ai_chatbot.utils.database import get_supabase_client


def load_faq_answers():
    """
    Load FAQ responses from Supabase.
    Returns a dictionary of questions and answers.
    """
    supabase = get_supabase_client()
    response = supabase.table("faq_responses").select("question, answer").execute()
    return {item["question"]: item["answer"] for item in response.data}
