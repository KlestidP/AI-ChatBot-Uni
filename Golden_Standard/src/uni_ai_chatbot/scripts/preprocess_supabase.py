import logging
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_mistralai import MistralAIEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore

from uni_ai_chatbot.configurations.config import MISTRAL_API_KEY
from uni_ai_chatbot.utils.database import get_supabase_client
from uni_ai_chatbot.data.resources import load_faq_answers
from uni_ai_chatbot.data.campus_map_data import load_campus_map
from uni_ai_chatbot.data.locker_hours_loader import load_locker_hours

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY is not set in environment variables")


def create_documents():
    """Create documents from FAQ, campus data, and locker data with tool classifications"""
    documents = []
    logger.info("Loading FAQ data...")

    # Add FAQ data as documents
    faq_data = load_faq_answers()
    for question, answer in faq_data.items():
        doc_content = f"Question: {question}\nAnswer: {answer}"
        documents.append(Document(
            page_content=doc_content,
            metadata={"type": "faq", "question": question, "tool": "qa"}
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
                "id": location['id'],
                "tool": "location"
            }
        ))

    logger.info(f"Loaded {len(campus_data)} campus locations")

    # Add locker hours data as documents
    logger.info("Loading locker data...")
    locker_data = load_locker_hours()
    for record in locker_data:
        college_name = record["colleges"]["name"] if record.get("colleges") else "Unknown"
        day_name = record["days"]["name"] if record.get("days") else "Unknown"
        basement = record["basement"] if record.get("basement") else "Unknown"

        if record.get("time_ranges"):
            time_info = f"{record['time_ranges']['start_time']} - {record['time_ranges']['end_time']}"
        else:
            time_info = "Hours not specified"

        doc_content = f"Locker access for {college_name}, {day_name}, Basement {basement}: {time_info}"
        documents.append(Document(
            page_content=doc_content,
            metadata={
                "type": "locker",
                "college": college_name,
                "day": day_name,
                "basement": basement,
                "tool": "locker"
            }
        ))

    logger.info(f"Loaded {len(locker_data)} locker hours records")
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
    supabase_client = get_supabase_client()

    logger.info("Storing embeddings in Supabase...")

    # Fix: Use a safer approach to clear existing documents
    try:
        # First, check if the table has any documents
        response = supabase_client.table("documents").select("id").limit(1).execute()

        if response and hasattr(response, 'data') and len(response.data) > 0:
            logger.info("Clearing existing documents...")
            # Use a safer approach to delete all documents - delete them in batches
            # with a true condition rather than no condition
            supabase_client.table("documents").delete().neq("id", 0).execute()
    except Exception as e:
        logger.warning(f"Error clearing existing documents: {e}")
        logger.info("Proceeding to add new documents anyway...")

    # Create a new vector store
    try:
        logger.info(f"Adding {len(split_docs)} documents to vector store...")
        vector_store = SupabaseVectorStore.from_documents(
            documents=split_docs,
            embedding=embeddings,
            client=supabase_client,
            table_name="documents",
            query_name="match_documents"
        )
        logger.info("Embeddings stored successfully in Supabase")
        return vector_store
    except Exception as e:
        logger.error(f"Error storing documents in vector store: {e}")
        raise


if __name__ == "__main__":
    try:
        # First check if setup was done
        from uni_ai_chatbot.scripts.setup_pgvector import setup_pgvector

        setup_pgvector()

        # Then process and save documents
        vector_store = process_and_save_to_supabase()
        print("Successfully created and saved embeddings to Supabase")
    except Exception as e:
        logger.error(f"Error preprocessing documents: {e}")
        raise