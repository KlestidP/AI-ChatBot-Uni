import logging
import re
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# List of university-related keywords to help identify relevant queries
UNIVERSITY_KEYWORDS = {
    'university', 'campus', 'college', 'class', 'course', 'professor', 'lecture', 'semester',
    'student', 'study', 'library', 'exam', 'assignment', 'homework', 'schedule', 'degree',
    'dormitory', 'dormitories', 'hall', 'locker', 'servery', 'dining', 'food', 'cafeteria',
    'constructor', 'krupp', 'mercator', 'nordmetall', 'c3', 'bremen', 'advisor', 'academia',
    'handbook', 'syllabus', 'printer', 'printing', 'coffee bar', 'basement', 'building',
    'registration', 'enrollment', 'credit', 'major', 'minor', 'faculty', 'sport', 'club',
    'event', 'scholarship', 'residence', 'permit', 'visa', 'document', 'certificate',
    'tuition', 'fee', 'payment', 'lab', 'laboratory', 'workshop', 'seminar', 'academic',
    'program', 'orientation', 'semester ticket', 'services', 'office', 'grade', 'housing',
    'accommodation', 'where is', 'how to', 'when is', 'where can', 'who is', 'what is', 'can i',
    'ify', 'irc', 'reimer', 'lükens', 'ocean lab', 'research', 'library', 'center', 'canteen',
    'mensa', 'jacobs'  # Include legacy name Jacobs University
}

# Non-university topics to filter out
NON_UNIVERSITY_TOPICS = [
    # Politics
    r'\b(politic|election|vote|president|party|democrat|republican|congress|parliament)\b',

    # Entertainment
    r'\b(movie|film|tv show|television|netflix|actor|actress|celebrity|hollywood)\b',

    # Sports (non-university)
    r'\b(nba|nfl|mlb|premier league|champions league|world cup|olympics|team)\b',

    # Technology (consumer)
    r'\b(iphone|android|samsung|google|facebook|twitter|instagram|tiktok|snapchat)\b',

    # Finance/cryptocurrency
    r'\b(stock market|bitcoin|ethereum|cryptocurrency|crypto|investment|forex|trading)\b',

    # Violence/weapons
    r'\b(gun|weapon|murder|bomb|terrorist|kill|attack)\b',

    # Adult content
    r'\b(sex|porn|naked|nude|explicit|adult)\b',

    # Drugs/alcohol (non-medical)
    r'\b(weed|marijuana|cocaine|heroin|drug dealer|getting high|getting drunk)\b',

    # Gaming/entertainment
    r'\b(playstation|xbox|nintendo|gaming|game)\b',
]


def is_university_related(query: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a query is university-related.

    Args:
        query: The text to check

    Returns:
        Tuple containing:
        - Boolean indicating if query is university-related
        - Reason for rejection if not university-related, None otherwise
    """
    # Convert to lowercase for easier matching
    text = query.lower()

    # Check for obvious non-university topics first
    for pattern in NON_UNIVERSITY_TOPICS:
        if re.search(pattern, text):
            matched = re.search(pattern, text).group(0)
            return False, f"Query contains non-university topic: '{matched}'"

    # Look for university keywords
    for keyword in UNIVERSITY_KEYWORDS:
        if keyword in text:
            return True, None

    # Check for directional queries that might be university-related
    if any(phrase in text for phrase in ['where is', 'how do i get to', 'how to find', 'direction to']):
        return True, None

    # Check for time-related queries that might be about university schedules
    if any(phrase in text for phrase in ['when is', 'what time', 'hours', 'schedule']):
        return True, None

    # If no university keywords found and not a clear directional or time query
    return False, "Query doesn't appear to be related to university topics"