import re
from typing import Tuple, List
from uni_ai_chatbot.services.handbook_service import MAJOR_ABBREVIATIONS

# List of university-related keywords
UNIVERSITY_KEYWORDS = [
    # Campus locations
    "campus", "college", "hall", "lab", "servery", "library", "office", "building", "lecture", "room",
    "theater", "centre", "center", "circle", "commons", "lounge", "study", "space", "cafe", "bar",

    # University services
    "registration", "enrollment", "course", "class", "professor", "ta", "teacher", "degree", "program",
    "major", "minor", "study", "research", "admission", "semester", "module", "credit", "grade",
    "exam", "midterm", "final", "project", "assignment", "homework", "thesis", "dissertation",
    "tuition", "fee", "scholarship", "financial aid", "dorm", "housing", "meal", "plan", "id",
    "card", "email", "account", "laundry", "printer", "copy", "transportation", "bus", "shuttle",

    # Course and prerequisite terms (ADDED)
    "prerequisite", "prerequisites", "pre-requisite", "pre-requisites", "corequisite", "co-requisite",
    "requirement", "requirements", "required", "mandatory", "optional", "elective", "core",
    "foundation", "advanced", "introductory", "intermediate", "specialization", "pre requisite", "pre requisites",
    "co requisite", "co requisites", "corequisites", "co-requisites"

    # University organizations
    "student", "faculty", "staff", "alumni", "club", "organization", "association", "union",
    "committee", "board", "council", "group", "team", "department", "school", "college",
    "administration", "president", "dean", "provost", "chair", "director", "professor",

    # University events
    "orientation", "graduation", "commencement", "ceremony", "lecture", "seminar", "workshop",
    "conference", "symposium", "fair", "festival", "concert", "performance", "game", "match",
    "tournament", "competition", "championship", "award", "celebration", "reception", "party",

    # University documents
    "transcript", "diploma", "certificate", "letter", "recommendation", "application", "form",
    "handbook", "syllabus", "curriculum", "schedule", "calendar", "map", "directory", "guideline",
    "policy", "rule", "regulation", "requirement", "deadline", "date", "time", "hour",

    # Constructor University specific
    "constructor", "jacobs", "nord", "metall", "college", "krupp", "mercator", "servery",
    "c3", "east", "west", "north", "south", "hall", "library", "irc", "campus", "bremen",
    "reimar", "lüst", "campusnet", "oceanlab", "res", "co", "rlc", "university",

    # Administrative terms
    "registrar", "bursar", "advisor", "counselor", "international", "residence", "permit",
    "visa", "insurance", "health", "medical", "doctor", "nurse", "clinic", "hospital",
    "emergency", "security", "safety", "police", "fire", "ambulance", "lost", "found",

    # Academic terms
    "lecture", "tutorial", "lab", "seminar", "workshop", "course", "class", "professor",
    "teacher", "instructor", "ta", "teaching", "assistant", "dean", "chair", "department",
    "faculty", "staff", "student", "undergraduate", "graduate", "phd", "master", "bachelor",
    "research", "paper", "publication", "journal", "conference", "grant", "funding",

    # Educational terms
    "assignment", "homework", "project", "report", "essay", "paper", "exam", "test", "quiz",
    "midterm", "final", "grade", "gpa", "credit", "unit", "requirement", "elective", "core",
    "mandatory", "optional", "prerequisite", "corequisite", "syllabus", "rubric", "evaluation",

    # Facilities
    "housing", "dormitory", "dorm", "room", "apartment", "flat", "bathroom", "shower", "toilet",
    "kitchen", "laundry", "washer", "dryer", "gym", "fitness", "sport", "field", "court",
    "pool", "track", "park", "garden", "cafeteria", "dining", "restaurant", "food", "meal",

    # Technology
    "wifi", "internet", "network", "email", "account", "password", "login", "computer", "laptop",
    "printer", "scanner", "software", "hardware", "app", "website", "portal", "online", "digital",

    # Transportation
    "parking", "lot", "space", "permit", "car", "bike", "bicycle", "bus", "shuttle", "train",
    "tram", "station", "stop", "airport", "ticket", "pass", "route", "schedule", "time",

    # Financial
    "tuition", "fee", "payment", "bill", "invoice", "refund", "scholarship", "grant", "loan",
    "financial", "aid", "bursary", "stipend", "salary", "wage", "tax", "budget", "cost",

    # Events
    "orientation", "graduation", "commencement", "ceremony", "reception", "party", "celebration",
    "festival", "concert", "performance", "show", "exhibition", "display", "presentation",
    "lecture", "talk", "speech", "debate", "discussion", "forum", "panel", "roundtable",

    # Student Life
    "club", "organization", "society", "group", "team", "activity", "event", "social",
    "cultural", "political", "religious", "spiritual", "volunteer", "service", "community",
    "outreach", "leadership", "development", "career", "job", "internship", "coop", "placement",

    # Administration
    "policy", "procedure", "rule", "regulation", "guideline", "standard", "code", "conduct",
    "discipline", "violation", "sanction", "penalty", "fine", "warning", "probation", "suspension",
    "expulsion", "dismissal", "termination", "resignation", "retirement", "leave", "absence",

    # Documents
    "form", "application", "petition", "appeal", "request", "proposal", "nomination", "referendum",
    "survey", "questionnaire", "evaluation", "assessment", "review", "audit", "inspection",
    "investigation", "inquiry", "report", "record", "file", "folder", "document", "certificate",
    "letter", "memo", "notice", "announcement", "bulletin", "newsletter", "brochure", "flyer",

    # Time
    "semester", "term", "quarter", "year", "session", "period", "duration", "deadline", "date",
    "time", "schedule", "calendar", "appointment", "meeting", "consultation", "office hour",
    "day", "week", "month", "weekend", "holiday", "break", "vacation", "recess", "spring",
    "summer", "fall", "autumn", "winter", "morning", "afternoon", "evening", "night"
]

# List of university-specific locations
UNIVERSITY_LOCATIONS = [
    "campus", "library", "servery", "dining hall", "cafeteria", "dining", "restaurant", "food",
    "college", "hall", "dormitory", "dorm", "apartment", "flat", "housing", "residence",
    "classroom", "lecture", "theater", "studio", "lab", "laboratory", "workshop", "office",
    "administration", "building", "center", "centre", "plaza", "square", "park", "garden",
    "field", "court", "pool", "gym", "fitness", "recreation", "sport", "athletic", "stadium",
    "auditorium", "theater", "theatre", "performance", "gallery", "museum", "exhibition",
    "bookstore", "shop", "store", "market", "convenience", "pharmacy", "clinic", "health",
    "medical", "hospital", "doctor", "nurse", "counselor", "advisor", "career", "job",
    "parking", "lot", "garage", "transportation", "bus", "shuttle", "train", "station",
    "stop", "terminal", "airport", "port", "dock", "locker", "bathroom", "restroom",
    "shower", "toilet", "laundry", "washer", "dryer", "kitchen", "dining", "lounge",
    "common", "area", "room", "space", "hall", "corridor", "elevator", "stair", "exit",
    "entrance", "door", "window", "roof", "floor", "wall", "ceiling", "foundation", "basement"
]


def is_university_related(query: str) -> Tuple[bool, str]:
    """
    Check if a query is related to university topics.

    Args:
        query: User query string

    Returns:
        Tuple of (is_relevant, reason)
    """
    if not query:
        return False, "Empty query"

    # Convert to lowercase for case-insensitive matching
    query_lower = query.lower()

    # PRIORITY CHECK: Teaching/Professor queries are ALWAYS university-related
    teaching_patterns = [
        r"who (teaches|is teaching|taught)",
        r"who (is|are) the (professor|instructor|teacher)",
        r"professor for",
        r"instructor for",
        r"teacher for",
        r"taught by",
        r"teaching assistant",
        r"when is .* taught",
        r"who gives",
        r"who offers"
    ]

    for pattern in teaching_patterns:
        if re.search(pattern, query_lower):
            return True, "Contains teaching/professor query pattern"

    # SPECIAL CASE: Academic queries about potential courses
    # These words indicate the query is about academic matters
    academic_context_words = [
        "prerequisite", "pre-requisite", "requirement", "required",
        "course", "class", "module", "program", "credit", "ects",
        "professor", "instructor", "exam", "assignment", "syllabus",
        "teaches", "teaching", "taught", "lecture", "tutorial",
        "enrollment", "enroll", "register", "registration",
        "grade", "grading", "assessment", "evaluation",
        "homework", "project", "thesis", "dissertation"
    ]

    # Common course/subject names that might appear in queries
    # Extended list to be more inclusive
    potential_course_names = [
        # Computer Science courses
        "operating systems", "database", "databases", "algorithms", "data structures",
        "networks", "networking", "programming", "software", "hardware",
        "compiler", "compilers", "architecture", "security", "cryptography",
        "machine learning", "artificial intelligence", "ai", "ml", "robotics",
        "web development", "mobile development", "cloud computing",
        "distributed systems", "parallel computing", "computer graphics",
        "human computer interaction", "hci", "software engineering",

        # Math courses
        "mathematics", "calculus", "algebra", "statistics", "probability",
        "discrete math", "linear algebra", "differential equations",
        "numerical methods", "optimization", "geometry",

        # Science courses
        "physics", "chemistry", "biology", "biochemistry", "biophysics",
        "mechanics", "thermodynamics", "electromagnetics", "quantum",
        "organic chemistry", "inorganic chemistry", "analytical chemistry",

        # Engineering courses
        "engineering", "circuits", "electronics", "signals", "systems",
        "control systems", "power systems", "communications",
        "materials", "statics", "dynamics", "fluids",

        # Business/Social Science courses
        "economics", "microeconomics", "macroeconomics", "finance",
        "accounting", "marketing", "management", "psychology",
        "sociology", "anthropology", "political science",

        # Other academic subjects
        "english", "writing", "literature", "history", "philosophy",
        "ethics", "languages", "german", "spanish", "french"
    ]

    # If query contains academic context word, it's likely university-related
    has_academic_context = any(word in query_lower for word in academic_context_words)

    # Check if query mentions something that could be a course
    mentions_potential_course = any(course in query_lower for course in potential_course_names)

    # If it has academic context OR mentions a potential course with a question word, accept it
    question_words = ["who", "what", "when", "where", "how", "why", "which", "can", "do", "does", "is", "are"]
    starts_with_question = any(query_lower.startswith(word) for word in question_words)

    if has_academic_context or (mentions_potential_course and starts_with_question):
        return True, "Contains academic context or course-related question"

    # Check for programs and abbreviations
    for abbr, full_name in MAJOR_ABBREVIATIONS.items():
        if (f" {abbr} " in f" {query_lower} " or
                query_lower.startswith(f"{abbr} ") or
                query_lower.endswith(f" {abbr}") or
                abbr == query_lower.strip()):
            return True, f"Contains program abbreviation: {abbr}"

        if full_name.lower() in query_lower:
            return True, f"Contains program name: {full_name}"

    # Check for university keywords
    for keyword in UNIVERSITY_KEYWORDS:
        if keyword.lower() in query_lower:
            return True, f"Contains university keyword: {keyword}"

    # Check for university locations
    for location in UNIVERSITY_LOCATIONS:
        if location.lower() in query_lower:
            return True, f"Contains university location: {location}"

    # Educational question indicators - MORE PATTERNS
    education_question_patterns = [
        r"how (do|can|to) (i|we|you) (get|find|access|use|register|sign up|apply)",
        r"where (is|are|can i find) .{3,}",
        r"what (is|are) .{3,} (hour|time|schedule|deadline|requirement|policy|procedure)",
        r"when (is|are|does|do) .{3,} (open|close|start|end|begin|finish|due|happen|taught|offered)",
        r"who (is|are|do i) .{3,} (contact|talk to|ask|professor|teacher|instructor|teaches|teaching)",
        r"do (i|we|you) need .{3,} (to|for)",
        r"can (i|we|you) .{3,} (get|find|access|use|register|sign up|apply|take|enroll)",
        # Specific patterns for prerequisites and requirements
        r"what.*(prerequisite|pre-requisite|requirement).*for",
        r"prerequisite.*for",
        r"requirement.*for",
        r"do i need.*before",
        r"what.*need.*before",
        r"required.*for",
        # Teaching-related patterns
        r"who.*teach",
        r"taught by",
        r"professor.*for",
        r"instructor.*for"
    ]

    for pattern in education_question_patterns:
        if re.search(pattern, query_lower):
            return True, f"Contains educational question pattern"

    # Check for academic terms
    academic_terms = [
        "grade", "course", "class", "exam", "test", "quiz", "homework", "assignment",
        "project", "paper", "thesis", "dissertation", "research", "study", "graduation",
        "degree", "major", "minor", "concentration", "specialization", "program",
        "curriculum", "syllabus", "credit", "unit", "hour", "semester", "term", "quarter",
        "year", "session", "lecture", "tutorial", "lab", "seminar", "workshop", "studio",
        "practicum", "internship", "coop", "placement", "fieldwork", "clinical", "residency",
        "prerequisite", "prerequisites", "pre-requisite", "pre-requisites",
        "corequisite", "co-requisite", "requirement", "requirements",
        "professor", "instructor", "teacher", "lecturer", "teaching"
    ]

    for term in academic_terms:
        if f" {term} " in f" {query_lower} " or query_lower.startswith(f"{term} ") or query_lower.endswith(f" {term}"):
            return True, f"Contains academic term: {term}"

    # Final catch-all: If query is asking about ANYTHING being taught/offered/given
    if re.search(r"(taught|offered|given|teaches|teaching|professor|instructor)", query_lower):
        return True, "Contains teaching-related terms"

    # Default to not related
    return False, "No university-related keywords or patterns detected"