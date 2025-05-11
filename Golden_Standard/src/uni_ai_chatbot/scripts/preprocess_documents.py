import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_mistralai import MistralAIEmbeddings

from uni_ai_chatbot.data.resources import load_faq_answers
from uni_ai_chatbot.data.campus_map_data import load_campus_map

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")

if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY is not set in environment variables")


def get_index_path() -> str:
    """Get the full file path to save the FAISS index, relative to the src directory."""
    project_root = Path(__file__).resolve().parents[2]
    vectorstore_dir = project_root / "uni_ai_chatbot" / "data" / "vectorstore"
    vectorstore_dir.mkdir(parents=True, exist_ok=True)
    return str(vectorstore_dir / "index.faiss")


def create_documents():
    """Create documents from FAQ and campus data"""
    documents = []
    logger.info("Loading FAQ data...")

    # Add FAQ data as documents
    faq_data = load_faq_answers()
    for question, answer in faq_data.items():
        doc_content = f"Question: {question}\nAnswer: {answer}"
        documents.append(Document(page_content=doc_content))

    logger.info(f"Loaded {len(faq_data)} FAQ entries")

    # Add campus location data as documents
    logger.info("Loading campus data...")
    campus_data = load_campus_map()
    for location in campus_data:
        doc_content = f"Location: {location['name']}\n"

        if location.get('tags'):
            doc_content += f"Features: {location['tags']}\n"

        if location.get('aliases'):
            doc_content += f"Also known as: {location['aliases']}\n"

        doc_content += f"Address: {location.get('address', 'Unknown')}"
        documents.append(Document(page_content=doc_content))

    logger.info(f"Loaded {len(campus_data)} campus locations")
    return documents


def process_and_save_index():
    """Process documents and save FAISS index"""
    logger.info("Creating documents...")
    documents = create_documents()

    logger.info("Splitting documents...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=200,
        chunk_overlap=20,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    split_docs = text_splitter.split_documents(documents)
    logger.info(f"Created {len(split_docs)} document chunks")

    logger.info("Creating embeddings...")
    embeddings = MistralAIEmbeddings(api_key=MISTRAL_API_KEY)

    logger.info("Building vector store...")
    vector_store = FAISS.from_documents(split_docs, embeddings)

    # Save the FAISS index
    index_path = get_index_path()
    logger.info(f"Saving FAISS index to {index_path}")
    vector_store.save_local(index_path)

    logger.info("FAISS index saved successfully")
    return index_path


if __name__ == "__main__":
    try:
        index_path = process_and_save_index()
        print(f"Successfully created and saved FAISS index to {index_path}")
    except Exception as e:
        logger.error(f"Error preprocessing documents: {e}")
        raise
