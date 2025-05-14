import logging
import io
import requests
import PyPDF2
from typing import List
from langchain_core.documents import Document

from uni_ai_chatbot.data.handbook_loader import load_handbooks

logger = logging.getLogger(__name__)


def process_handbooks(max_chunk_size=500) -> List[Document]:
    """
    Process handbook PDFs into document chunks suitable for embedding

    Args:
        max_chunk_size: Maximum size in characters for each chunk

    Returns:
        List of document objects
    """
    documents = []

    try:
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
                handbook_text = extract_clean_text(pdf_reader)

                # Create smaller chunks for better embedding and retrieval
                chunks = chunk_text(handbook_text, max_chunk_size)

                # Create documents from chunks
                for i, chunk in enumerate(chunks):
                    if len(chunk) < 50:  # Skip very small chunks
                        continue

                    documents.append(Document(
                        page_content=chunk,
                        metadata={
                            "type": "handbook",
                            "major": handbook['major'],
                            "file_name": handbook['file_name'],
                            "chunk_id": i,
                            "tool": "handbook"
                        }
                    ))

                logger.info(f"Processed {handbook['file_name']} into {len(chunks)} chunks")

            except Exception as e:
                logger.error(f"Error processing {handbook['file_name']}: {e}")

    except Exception as e:
        logger.error(f"Error in handbook processing: {e}")

    return documents


def extract_clean_text(pdf_reader):
    """Extract and clean text from PDF"""
    text = ""
    for page_num in range(len(pdf_reader.pages)):
        try:
            page_text = pdf_reader.pages[page_num].extract_text()
            if page_text:
                text += page_text + "\n"
        except Exception as e:
            logger.warning(f"Error extracting text from page {page_num}: {e}")

    # Clean up text - remove excessive whitespace and normalize
    import re
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('\0', '')  # Remove null bytes that might cause issues

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