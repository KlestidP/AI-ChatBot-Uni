import re
from typing import List, Dict, Any

def extract_feature_keywords(text: str) -> List[str]:
    """
    Extract keywords from user query that might correspond to features

    Args:
        text: User query text

    Returns:
        List of potential feature keywords
    """
    # Common feature-related words to look for
    feature_patterns = [
        r'\b(print(?:ing|er)?)\b',
        r'\b(stud(?:y|ying))\b',
        r'\b(food|eat(?:ing)?|dining|meal)\b',
        r'\b(coffee)\b',
        r'\b(ify)\b',  # ify-specific keyword
        r'\b(quiet)\b'
    ]

    keywords = []
    for pattern in feature_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        keywords.extend([m.lower() for m in matches if m])

    return keywords

def find_locations_by_feature(locations: List[Dict[str, Any]], feature_keywords: List[str]) -> List[Dict[str, Any]]:
    """
    Find locations based on feature keywords that may match tags

    Args:
        locations: List of location dictionaries
        feature_keywords: List of keywords to match against tags

    Returns:
        List of locations that match any of the keywords
    """
    feature_keywords = [kw.lower() for kw in feature_keywords]
    matches = []

    # Feature matching logic - map common request terms to tags
    feature_to_tag_map = {
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
    search_tags = set()
    for keyword in feature_keywords:
        if keyword in feature_to_tag_map:
            search_tags.add(feature_to_tag_map[keyword])
        else:
            search_tags.add(keyword)  # Keep original keyword as well

    # Find locations with matching tags
    for location in locations:
        if not location.get('tags'):
            continue

        location_tags = set([tag.strip().lower() for tag in location['tags'].split(',')])
        if any(tag in location_tags for tag in search_tags):
            matches.append(location)

    return matches
