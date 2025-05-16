import logging
import io
import re
import requests
import PyPDF2
from typing import List, Dict, Any, Optional
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class CourseInfo:
    """Class to store structured course information"""

    def __init__(self, code: str = "", name: str = "",
                 credits: str = "", mandatory: bool = False,
                 year: str = "", semester: str = ""):
        self.code = code
        self.name = name
        self.credits = credits
        self.mandatory = mandatory
        self.year = year
        self.semester = semester

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "credits": self.credits,
            "mandatory": self.mandatory,
            "year": self.year,
            "semester": self.semester
        }


def process_handbooks(max_chunk_size=500) -> List[Document]:
    """
    Process handbook PDFs into document chunks suitable for embedding
    with enhanced structure recognition and metadata

    Args:
        max_chunk_size: Maximum size in characters for each chunk

    Returns:
        List of document objects
    """
    documents = []

    try:
        from uni_ai_chatbot.data.handbook_loader import load_handbooks
        handbooks = load_handbooks()
        logger.info(f"Processing {len(handbooks)} handbooks...")

        for handbook in handbooks:
            if not handbook.get('url'):
                continue

            try:
                # Download the PDF content
                response = requests.get(handbook['url'])
                if response.status_code != 200:
                    logger.warning(f"Failed to download {handbook['file_name']}: {response.status_code}")
                    continue

                pdf_content = response.content

                # Process PDF text
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))

                # First, extract the full text to analyze structure
                handbook_text = extract_clean_text(pdf_reader)

                # Identify curriculum structure and course requirements
                curriculum_sections = identify_curriculum_sections(handbook_text)
                course_requirements = extract_course_requirements(handbook_text)

                # Create specific documents for curriculum and requirements
                if curriculum_sections:
                    for section_name, section_text in curriculum_sections.items():
                        documents.append(Document(
                            page_content=section_text,
                            metadata={
                                "type": "handbook_curriculum",
                                "major": handbook['major'],
                                "file_name": handbook['file_name'],
                                "section": section_name,
                                "tool": "handbook"
                            }
                        ))

                # Add structured course requirement information
                if course_requirements:
                    for year, year_courses in course_requirements.items():
                        content = f"Required courses for {year} in {handbook['major']}:\n\n"
                        content += "\n".join([f"- {course}" for course in year_courses])

                        documents.append(Document(
                            page_content=content,
                            metadata={
                                "type": "handbook_courses",
                                "major": handbook['major'],
                                "year": year,
                                "mandatory": True,
                                "tool": "handbook"
                            }
                        ))

                # Also create standard chunks for general information
                chunks = chunk_text(handbook_text, max_chunk_size)
                for i, chunk in enumerate(chunks):
                    if len(chunk) < 50:  # Skip very small chunks
                        continue

                    documents.append(Document(
                        page_content=chunk,
                        metadata={
                            "type": "handbook_general",
                            "major": handbook['major'],
                            "file_name": handbook['file_name'],
                            "chunk_id": i,
                            "tool": "handbook"
                        }
                    ))

                logger.info(
                    f"Processed {handbook['file_name']} into {len(chunks)} general chunks plus specialized sections")

            except Exception as e:
                logger.error(f"Error processing {handbook['file_name']}: {e}")

    except Exception as e:
        logger.error(f"Error in handbook processing: {e}")

    return documents


def identify_curriculum_sections(text: str) -> Dict[str, str]:
    """
    Identify and extract curriculum-related sections from handbook text

    Args:
        text: Full handbook text

    Returns:
        Dictionary of section name to section text
    """
    sections = {}

    # Common section headers for curriculum/required courses
    curriculum_headers = [
        r"(?:Curriculum|Study|Examination) (?:Plan|Structure)",
        r"(?:Required|Mandatory|Core) (?:Courses|Modules)",
        r"(?:Year|Semester) \d+[^\n]+(?:Courses|Modules)",
        r"CHOICE Modules?",
        r"CORE Modules?",
        r"CAREER Modules?"
    ]

    # Try to find these sections
    current_section = None
    current_text = []

    for line in text.split('\n'):
        # Check if this line might be a curriculum header
        is_header = False
        for pattern in curriculum_headers:
            if re.search(pattern, line, re.IGNORECASE):
                # If we were collecting a section, save it
                if current_section:
                    sections[current_section] = '\n'.join(current_text)

                # Start a new section
                current_section = line.strip()
                current_text = [line]
                is_header = True
                break

        # If not a header and we're collecting a section, add to current text
        if not is_header and current_section:
            current_text.append(line)

    # Save the last section if any
    if current_section:
        sections[current_section] = '\n'.join(current_text)

    return sections


def extract_course_requirements(text: str) -> Dict[str, List[str]]:
    """
    Extract mandatory course requirements organized by year

    Args:
        text: Full handbook text

    Returns:
        Dictionary mapping year to list of required courses
    """
    requirements = {
        "First Year": [],
        "Second Year": [],
        "Third Year": [],
        "CHOICE Year": [],
        "CORE Year": [],
        "CAREER Year": []
    }

    # Look for course lists near relevant headers
    year_patterns = {
        "First Year": [r"First Year", r"Year 1", r"CHOICE"],
        "Second Year": [r"Second Year", r"Year 2", r"CORE"],
        "Third Year": [r"Third Year", r"Year 3", r"CAREER"],
        "CHOICE Year": [r"CHOICE Modules?", r"CHOICE Year"],
        "CORE Year": [r"CORE Modules?", r"CORE Year"],
        "CAREER Year": [r"CAREER Modules?", r"CAREER Year"]
    }

    # Patterns for mandatory course indicators
    mandatory_indicators = [
        r"[Mm]andatory",
        r"[Rr]equired",
        r"[Cc]ore",
        r"\(m,",
        r"\bm\s",
    ]

    # Course pattern: typically has a code or title followed by credits
    course_pattern = r"(?:[A-Z]{2,4}[-\s]?\d{3,4}[-\s]?[A-Z]?|[A-Z][a-z]+(?:\s[A-Z][a-z]+){1,5})(?:.*?(\d+(?:\.\d+)?\s*(?:CP|ECTS|Credit)s?))?)"

    # For each year pattern, try to find associated courses
    for year, patterns in year_patterns.items():
        for pattern in patterns:
            # Find sections that match this year pattern
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Extract a chunk of text following this header
                start_pos = match.end()
                chunk_end = min(start_pos + 2000, len(text))  # Look at next 2000 chars
                chunk = text[start_pos:chunk_end]

                # Look for courses in this chunk
                lines = chunk.split('\n')
                for line in lines:
                    # Check if line indicates a mandatory course
                    is_mandatory = any(re.search(indicator, line) for indicator in mandatory_indicators)

                    if is_mandatory:
                        # Try to extract course info
                        course_match = re.search(course_pattern, line)
                        if course_match:
                            course = course_match.group(0).strip()
                            if course and course not in requirements[year]:
                                requirements[year].append(course)

    return requirements


def extract_clean_text(pdf_reader):
    """Extract and clean text from PDF with better formatting preservation"""
    text = ""
    for page_num in range(len(pdf_reader.pages)):
        try:
            page_text = pdf_reader.pages[page_num].extract_text()
            if page_text:
                text += page_text + "\n\n"  # Add double newline to better separate pages
        except Exception as e:
            logger.warning(f"Error extracting text from page {page_num}: {e}")

    # Clean up text but preserve paragraph structure
    import re
    # Replace multiple newlines with double newline (preserve paragraphs)
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Replace sequences of spaces with single space
    text = re.sub(r' {2,}', ' ', text)
    # Remove null bytes that might cause issues
    text = text.replace('\0', '')

    return text


def chunk_text(text, chunk_size=500, overlap=50):
    """Split text into smaller chunks with overlap"""
    chunks = []

    # First try to split by double newlines (paragraphs)
    paragraphs = text.split('\n\n')
    current_chunk = ""

    for para in paragraphs:
        # If adding this paragraph would exceed chunk size, save current chunk and start a new one
        if len(current_chunk) + len(para) > chunk_size:
            if current_chunk:
                chunks.append(current_chunk)

            # If paragraph is larger than chunk size, split it further
            if len(para) > chunk_size:
                # Add paragraph chunks with overlap
                for i in range(0, len(para), chunk_size - overlap):
                    chunks.append(para[i:i + chunk_size])
            else:
                current_chunk = para
        else:
            # Add paragraph to current chunk
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para

    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk)

    return chunks