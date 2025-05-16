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
    Process handbook PDFs into document chunks with preserved structure
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
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_content))

                # Extract text with structure preservation
                structured_content = extract_structured_content(pdf_reader)

                # Create document chunks for each section
                for section in structured_content:
                    section_title = section['title']
                    section_content = section['content']
                    section_level = section['level']
                    section_number = section.get('number', '')

                    # Create chunks that include section title as context
                    chunks = create_contextual_chunks(section_content, section_title, max_chunk_size)

                    for i, chunk in enumerate(chunks):
                        documents.append(Document(
                            page_content=chunk,
                            metadata={
                                "type": "handbook_section",
                                "major": handbook['major'],
                                "file_name": handbook['file_name'],
                                "section_title": section_title,
                                "section_number": section_number,
                                "section_level": section_level,
                                "chunk_id": i,
                                "total_chunks": len(chunks),
                                "tool": "handbook"
                            }
                        ))

                logger.info(f"Processed {handbook['file_name']} into {len(documents)} structured chunks")

            except Exception as e:
                logger.error(f"Error processing {handbook['file_name']}: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Error in handbook processing: {e}", exc_info=True)

    return documents


def extract_structured_content(pdf_reader) -> List[Dict[str, Any]]:
    """
    Extract structured content from PDF with section headers
    """
    sections = []
    current_section = {"title": "Overview", "level": 0, "content": "", "number": ""}

    # Extract full text first
    full_text = ""
    for page_num in range(len(pdf_reader.pages)):
        try:
            page_text = pdf_reader.pages[page_num].extract_text()
            if page_text:
                full_text += page_text + "\n\n"
        except Exception as e:
            logger.warning(f"Error extracting text from page {page_num}: {e}")

    # Define patterns for section headers
    section_patterns = [
        # Match patterns like "1 Program Overview" or "1.1 Concept"
        r'\n(\d+(?:\.\d+)*)\s+([A-Z][A-Za-z\s\-]+)',
        # Match capitalized section headers
        r'\n([A-Z][A-Z\s]+(?:[A-Za-z\s\-]+))',
        # Match module headers
        r'\n(\d+\.\d+)\s+([A-Z][A-Za-z\s\&\-]+)'
    ]

    # Find section boundaries
    all_matches = []
    for pattern in section_patterns:
        for match in re.finditer(pattern, full_text):
            # Determine if this is a section number + title or just title
            if len(match.groups()) == 2:
                number, title = match.groups()
                level = number.count('.') + 1
            else:
                number = ""
                title = match.group(1)
                level = 1 if title.isupper() else 2

            all_matches.append({
                "position": match.start(),
                "title": title.strip(),
                "number": number,
                "level": level
            })

    # Sort matches by position in text
    all_matches.sort(key=lambda m: m["position"])

    # Create sections based on matches
    for i, match in enumerate(all_matches):
        # Determine section end
        if i < len(all_matches) - 1:
            section_text = full_text[match["position"]:all_matches[i + 1]["position"]]
        else:
            section_text = full_text[match["position"]:]

        sections.append({
            "title": match["title"],
            "number": match["number"],
            "level": match["level"],
            "content": section_text.strip()
        })

    # Handle case with no detected sections
    if not sections:
        sections.append({
            "title": "Handbook Content",
            "number": "",
            "level": 0,
            "content": full_text.strip()
        })

    return sections


def create_contextual_chunks(text: str, section_title: str, max_size: int) -> List[str]:
    """
    Create chunks with section context preserved
    """
    # Add section header to text
    section_header = f"SECTION: {section_title}\n\n"

    # Split text by paragraphs
    paragraphs = re.split(r'\n\s*\n', text)

    chunks = []
    current_chunk = section_header

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        # Check if adding this paragraph would exceed max size
        if len(current_chunk) + len(paragraph) + 2 <= max_size:
            current_chunk += paragraph + "\n\n"
        else:
            # Save current chunk and start a new one
            if current_chunk != section_header:
                chunks.append(current_chunk.strip())

            # If paragraph itself is too long, split it further
            if len(paragraph) > max_size - len(section_header):
                # Split long paragraph by sentences
                sentences = re.split(r'(?<=[.!?])\s+', paragraph)
                current_chunk = section_header

                for sentence in sentences:
                    if len(current_chunk) + len(sentence) + 2 <= max_size:
                        current_chunk += sentence + " "
                    else:
                        if current_chunk != section_header:
                            chunks.append(current_chunk.strip())
                        current_chunk = section_header + sentence + " "
            else:
                current_chunk = section_header + paragraph + "\n\n"

    # Add final chunk
    if current_chunk != section_header:
        chunks.append(current_chunk.strip())

    return chunks