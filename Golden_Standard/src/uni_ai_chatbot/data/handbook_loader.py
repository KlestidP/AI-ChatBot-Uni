from typing import List, Dict, Any
from uni_ai_chatbot.utils.database import get_supabase_client


def load_handbooks():
    """
    Load handbook files from Supabase storage bucket.

    Returns:
        List of dictionaries with handbook metadata and URLs
    """
    supabase = get_supabase_client()

    # List all files in the 'handbooks' bucket
    response = supabase.storage.from_('handbooks').list()

    if not response or isinstance(response, dict) and response.get('error'):
        raise Exception(f"Error fetching handbooks from storage: {response.get('error')}")

    handbooks = []

    for item in response:
        # Get file name and create signed URL for access
        file_name = item.get('name')
        if not file_name:
            continue

        # Extract major name from filename (assuming format like "computer_science_handbook.pdf")
        major = file_name.replace('_handbook.pdf', '').replace('_', ' ').title()

        # Generate signed URL with 24-hour expiration
        try:
            signed_url_result = supabase.storage.from_('handbooks').create_signed_url(
                file_name,
                86400  # 24 hours in seconds
            )

            signed_url = signed_url_result.get('signedURL') if isinstance(signed_url_result, dict) else None

            handbooks.append({
                'major': major,
                'file_name': file_name,
                'url': signed_url
            })
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error generating signed URL for {file_name}: {e}")

    return handbooks