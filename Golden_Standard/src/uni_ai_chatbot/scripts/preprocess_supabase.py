import os
import logging
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_mistralai import MistralAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from supabase import create_client

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
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY is not set in environment variables")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials not found in environment variables")


def create_documents():
    """Create documents from FAQ and campus data"""
    documents = []
    logger.info("Loading FAQ data...")

    # Add FAQ data as documents
    faq_data = load_faq_answers()
    for question, answer in faq_data.items():
        doc_content = f"Question: {question}\nAnswer: {answer}"
        documents.append(Document(
            page_content=doc_content,
            metadata={"type": "faq", "question": question}
        ))

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
        documents.append(Document(
            page_content=doc_content,
            metadata={
                "type": "location",
                "name": location['name'],
                "id": location['id']
            }
        ))

    logger.info(f"Loaded {len(campus_data)} campus locations")
    return documents


def process_and_save_to_supabase():
    """Process documents and save embeddings to Supabase vector store"""
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

    logger.info("Creating Supabase client...")
    supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

    logger.info("Storing embeddings in Supabase...")
    # First, clear the existing documents
    supabase_client.table("documents").delete().execute()
    
    # Create a new vector store
    vector_store = SupabaseVectorStore.from_documents(
        documents=split_docs,
        embedding=embeddings,
        client=supabase_client,
        table_name="documents",
        query_name="match_documents"
    )

    logger.info("Embeddings stored successfully in Supabase")
    return vector_store


if __name__ == "__main__":
    try:
        # First check if setup was done
        from setup_pgvector import setup_pgvector
        setup_pgvector()
        
        # Then process and save documents
        vector_store = process_and_save_to_supabase()
        print("Successfully created and saved embeddings to Supabase")
    except Exception as e:
        logger.error(f"Error preprocessing documents: {e}")
        raise