import os
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Supabase credentials
SUPABASE_URL: Optional[str] = os.environ.get("SUPABASE_URL")
SUPABASE_KEY: Optional[str] = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


def get_supabase_client() -> Client:
    """
    Initialize and return a Supabase client

    Returns:
        A configured Supabase client

    Raises:
        ValueError: If credentials are not found
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Supabase credentials not found in environment variables")

    return create_client(SUPABASE_URL, SUPABASE_KEY)


def load_campus_map() -> List[Dict[str, Any]]:
    """
    Load campus map data from Supabase

    Returns:
        List of dictionaries containing location information

    Raises:
        Exception: If there's an error fetching data
    """
    supabase: Client = get_supabase_client()

    # Query the campus_map table
    response = supabase.table("campus_map").select("*").execute()

    if hasattr(response, 'error') and response.error:
        raise Exception(f"Error fetching campus map data: {response.error}")

    return response.data


def find_locations_by_tag(locations: List[Dict[str, Any]], tag: str) -> List[Dict[str, Any]]:
    """
    Find all locations that have a specific tag

    Args:
        locations: List of location dictionaries
        tag: The tag to search for

    Returns:
        List of locations that contain the specified tag
    """
    results: List[Dict[str, Any]] = []
    for loc in locations:
        # Check if tags field exists and contains the tag
        if loc.get('tags') and tag in [t.strip() for t in loc['tags'].split(',')]:
            results.append(loc)
    return results


def find_location_by_name_or_alias(locations: List[Dict[str, Any]], query: str) -> Optional[Dict[str, Any]]:
    """
    Find a location by its name or alias (case-insensitive)
    Improved with more robust matching and better handling of partial matches

    Args:
        locations: List of location dictionaries
        query: The search term to look for

    Returns:
        The matching location dictionary, or None if no match found
    """
    if not query or not locations:
        return None

    query: str = query.lower().strip()

    # Strategy 1: Exact match on name
    for location in locations:
        if location['name'].lower() == query:
            return location

    # Strategy 2: Exact match on alias
    for location in locations:
        if location.get('aliases'):
            aliases: List[str] = [alias.strip().lower() for alias in location['aliases'].split(',')]
            if query in aliases:
                return location

    # Strategy 3: Partial match on name (whole word)
    for location in locations:
        loc_name_words: List[str] = location['name'].lower().split()
        query_words: List[str] = query.split()
        if any(word in loc_name_words for word in query_words):
            return location

    # Strategy 4: Partial match anywhere
    for location in locations:
        if query in location['name'].lower():
            return location

    # Strategy 5: Alias partial match
    for location in locations:
        if location.get('aliases'):
            aliases: List[str] = [alias.strip().lower() for alias in location['aliases'].split(',')]
            for alias in aliases:
                if query in alias or alias in query:
                    return location

    # Strategy 6: Word-by-word matching for aliases
    for location in locations:
        if location.get('aliases'):
            aliases: str = location['aliases'].lower()
            query_words: List[str] = query.split()
            if any(word in aliases for word in query_words if len(word) > 2):
                return location

    return None


def find_locations_by_feature(locations: List[Dict[str, Any]], feature_keywords: List[str]) -> List[Dict[str, Any]]:
    """
    Find locations based on feature keywords that may match tags

    Args:
        locations: List of location dictionaries
        feature_keywords: List of keywords to match against tags

    Returns:
        List of locations that match any of the keywords
    """
    feature_keywords: List[str] = [kw.lower() for kw in feature_keywords]
    matches: List[Dict[str, Any]] = []

    # Feature matching logic - map common request terms to tags
    feature_to_tag_map: Dict[str, str] = {
        "print": "printer",
        "printing": "printer",
        "eat": "food",
        "food": "food",
        "meal": "food",
        "dining": "food",
        "study": "study",
        "studying": "study",
        "quiet": "study",
        "coffee": "coffee",
        "cafeteria": "food",
        "ify": "ify"  # For "ify" specific queries
    }

    # Convert feature keywords to relevant tags
    search_tags: Set[str] = set()
    for keyword in feature_keywords:
        if keyword in feature_to_tag_map:
            search_tags.add(feature_to_tag_map[keyword])
        else:
            search_tags.add(keyword)  # Keep original keyword as well

    # Find locations with matching tags
    for location in locations:
        if not location.get('tags'):
            continue

        location_tags: Set[str] = set([tag.strip().lower() for tag in location['tags'].split(',')])
        if any(tag in location_tags for tag in search_tags):
            matches.append(location)

    return matches


def extract_feature_keywords(text: str) -> List[str]:
    """
    Extract keywords from user query that might correspond to features

    Args:
        text: User query text

    Returns:
        List of potential feature keywords
    """
    # Common feature-related words to look for
    feature_patterns: List[str] = [
        r'\b(print(?:ing|er)?)\b',
        r'\b(stud(?:y|ying))\b',
        r'\b(food|eat(?:ing)?|dining|meal)\b',
        r'\b(coffee)\b',
        r'\b(ify)\b',  # ify-specific keyword
        r'\b(quiet)\b'
    ]

    keywords: List[str] = []
    for pattern in feature_patterns:
        matches: List[str] = re.findall(pattern, text, re.IGNORECASE)
        keywords.extend([m.lower() for m in matches if m])

    return keywords


def extract_location_name(query: str) -> str:
    """
    Extract potential location name from a query

    Args:
        query: The user's input text

    Returns:
        The cleaned location name
    """
    # Remove common question words
    query = query.lower()
    for prefix in ["where is", "where's", "where can i find", "how do i get to", "find", "where"]:
        if query.startswith(prefix):
            query = query[len(prefix):].strip()

    # Remove question mark
    query = query.strip("?").strip()

    return query