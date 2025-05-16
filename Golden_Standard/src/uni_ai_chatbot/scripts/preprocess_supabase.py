import logging
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_mistralai import MistralAIEmbeddings

from uni_ai_chatbot.configurations.config import MISTRAL_API_KEY
from uni_ai_chatbot.utils.database import get_supabase_client
from uni_ai_chatbot.utils.custom_supabase import FixedSupabaseVectorStore
from uni_ai_chatbot.data.resources import load_faq_answers
from uni_ai_chatbot.data.campus_map_data import load_campus_map
from uni_ai_chatbot.data.locker_hours_loader import load_locker_hours
from uni_ai_chatbot.data.servery_hours_loader import load_servery_hours
from uni_ai_chatbot.data.handbook_processor import process_handbooks

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

if not MISTRAL_API_KEY:
    raise ValueError("MISTRAL_API_KEY is not set in environment variables")


def create_documents():
    """Create documents from FAQ, campus data, locker data, and handbooks with tool classifications"""
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

    # Add servery hours data as documents
    logger.info("Loading servery data...")
    servery_data = load_servery_hours()
    for record in servery_data:
        college_name = record["colleges"]["name"] if record.get("colleges") else "Unknown"
        day_name = record["days"]["name"] if record.get("days") else "Unknown"
        meal_type = record["meal_type"] if record.get("meal_type") else "Unknown"

        if record.get("time_ranges"):
            time_info = f"{record['time_ranges']['start_time']} - {record['time_ranges']['end_time']}"
        else:
            time_info = "Hours not specified"

        doc_content = f"Servery hours for {college_name}, {day_name}, {meal_type}: {time_info}"
        documents.append(Document(
            page_content=doc_content,
            metadata={
                "type": "servery",
                "college": college_name,
                "day": day_name,
                "meal_type": meal_type,
                "tool": "servery"
            }
        ))

    logger.info(f"Loaded {len(servery_data)} servery hours records")

    # Add handbook data as documents
    logger.info("Loading handbook data...")
    handbook_docs = process_handbooks(max_chunk_size=500)
    documents.extend(handbook_docs)
    logger.info(f"Loaded {len(handbook_docs)} handbook chunks")

    return documents


def process_and_save_to_supabase():
    """Process documents and save embeddings to Supabase vector store in batches"""
    logger.info("Creating documents...")
    documents = create_documents()

    logger.info("Splitting documents...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    split_docs = text_splitter.split_documents(documents)
    logger.info(f"Created {len(split_docs)} document chunks")

    logger.info("Creating embeddings...")
    embeddings = MistralAIEmbeddings(api_key=MISTRAL_API_KEY)

    logger.info("Creating Supabase client...")
    supabase_client = get_supabase_client()

    # Check for existing documents
    try:
        # Ask about dropping the table
        user_input = input("Drop the documents table and recreate it? This will delete ALL existing documents. (y/n): ")
        if user_input.lower() == 'y':
            delete_all_documents(supabase_client)

            # Ensure the table is recreated with the correct schema
            logger.info("Recreating documents table...")
            from uni_ai_chatbot.scripts.setup_pgvector import setup_pgvector
            setup_pgvector()
        else:
            logger.info("Skipping deletion, will add new documents to existing ones")
    except Exception as e:
        logger.warning(f"Error dropping table: {e}")
        user_input = input("Continue anyway and try to add new documents? (y/n): ")
        if user_input.lower() != 'y':
            logger.info("Aborting operation as requested")
            return

    # Process in smaller batches to avoid API limitations
    batch_size = 100  # Process 100 documents at a time
    total_docs = len(split_docs)

    logger.info(f"Adding {total_docs} documents to vector store in batches of {batch_size}...")

    for i in range(0, total_docs, batch_size):
        batch_end = min(i + batch_size, total_docs)
        current_batch = split_docs[i:batch_end]

        try:
            logger.info(
                f"Processing batch {i // batch_size + 1}/{(total_docs + batch_size - 1) // batch_size}: documents {i} to {batch_end - 1}")

            # Create embeddings for this batch
            batch_texts = [doc.page_content for doc in current_batch]
            batch_metadatas = [doc.metadata for doc in current_batch]

            # Add these documents to the vector store
            FixedSupabaseVectorStore.from_texts(
                texts=batch_texts,
                embedding=embeddings,
                metadatas=batch_metadatas,
                client=supabase_client,
                table_name="documents",
                query_name="match_documents"
            )

            logger.info(f"Successfully added batch {i // batch_size + 1}")

        except Exception as e:
            logger.error(f"Error processing batch {i // batch_size + 1}: {e}")
            # Continue with the next batch instead of failing everything

    logger.info("Embeddings stored successfully in Supabase")
    return None  # Don't return the vector store since we're creating it in batches


def delete_all_documents(supabase_client):
    """Delete all documents by dropping the table completely - setup_pgvector will recreate it"""
    try:
        logger.info("Dropping documents table...")

        # Drop the table via SQL
        try:
            drop_response = supabase_client.rpc('execute_sql', {'sql': 'DROP TABLE IF EXISTS documents;'}).execute()
            logger.info("Successfully dropped documents table")
            return "All (table dropped)"
        except Exception as sql_error:
            logger.error(f"Failed to drop table via SQL: {sql_error}")
            logger.error("You may need to manually run this SQL in the Supabase SQL editor:")
            logger.error("DROP TABLE IF EXISTS documents;")
            raise Exception("Cannot drop table - SQL execution failed")

    except Exception as e:
        logger.error(f"Error dropping documents table: {e}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Response: {e.response.text}")
        raise Exception(f"Failed to drop documents table: {str(e)}")


def update_handbook_embeddings():
    """Updates only the handbook documents in the vector store with improved structure preservation"""
    try:
        logger.info("Creating embeddings...")
        embeddings = MistralAIEmbeddings(api_key=MISTRAL_API_KEY)

        logger.info("Creating Supabase client...")
        supabase_client = get_supabase_client()

        # Delete existing handbook documents first
        logger.info("Deleting existing handbook documents...")
        try:
            # Use RPC to delete documents with tool=handbook metadata
            delete_query = "DELETE FROM documents WHERE metadata->>'tool' = 'handbook';"
            supabase_client.rpc('execute_sql', {'sql': delete_query}).execute()
            logger.info("Successfully deleted existing handbook documents")
        except Exception as e:
            logger.error(f"Error deleting existing handbook documents: {e}")
            logger.info("Trying alternative deletion method...")
            # Try to delete documents one by one if bulk deletion fails
            try:
                result = supabase_client.table("documents").select("id").eq("metadata->>tool", "handbook").execute()
                if hasattr(result, 'data') and result.data:
                    for doc in result.data:
                        supabase_client.table("documents").delete().eq("id", doc['id']).execute()
                logger.info(f"Deleted {len(result.data) if hasattr(result, 'data') else 0} handbook documents")
            except Exception as e2:
                logger.error(f"Failed to delete documents: {e2}")
                user_input = input("Continue anyway? (y/n): ")
                if user_input.lower() != 'y':
                    return

        # Process handbooks with improved structure preservation
        logger.info("Processing handbooks with improved structure...")
        handbook_documents = process_handbooks(max_chunk_size=500)
        logger.info(f"Generated {len(handbook_documents)} handbook document chunks")

        # Process in batches to avoid API limitations
        batch_size = 50  # Process 50 documents at a time
        total_docs = len(handbook_documents)

        logger.info(f"Adding {total_docs} handbook documents to vector store in batches of {batch_size}...")

        for i in range(0, total_docs, batch_size):
            batch_end = min(i + batch_size, total_docs)
            current_batch = handbook_documents[i:batch_end]

            try:
                logger.info(
                    f"Processing batch {i // batch_size + 1}/{(total_docs + batch_size - 1) // batch_size}: documents {i} to {batch_end - 1}")

                # Create embeddings for this batch
                batch_texts = [doc.page_content for doc in current_batch]
                batch_metadatas = [doc.metadata for doc in current_batch]

                # Add these documents to the vector store
                FixedSupabaseVectorStore.from_texts(
                    texts=batch_texts,
                    embedding=embeddings,
                    metadatas=batch_metadatas,
                    client=supabase_client,
                    table_name="documents",
                    query_name="match_documents"
                )

                logger.info(f"Successfully added batch {i // batch_size + 1}")

            except Exception as e:
                logger.error(f"Error processing batch {i // batch_size + 1}: {e}")
                # Continue with the next batch instead of failing everything

        logger.info("Handbook embeddings updated successfully in Supabase")
        return True

    except Exception as e:
        logger.error(f"Error updating handbook embeddings: {e}")
        return False


if __name__ == "__main__":
    try:
        # Parse command line arguments
        import argparse

        parser = argparse.ArgumentParser(description="Process and save embeddings to Supabase")
        parser.add_argument("--handbooks-only", action="store_true", help="Update only handbook embeddings")
        args = parser.parse_args()

        # First check if setup was done
        from uni_ai_chatbot.scripts.setup_pgvector import setup_pgvector

        setup_pgvector()

        if args.handbooks_only:
            # Only update handbook embeddings
            print("Updating only handbook embeddings...")
            update_handbook_embeddings()
        else:
            # Process and save all documents
            vector_store = process_and_save_to_supabase()

        print("Successfully created and saved embeddings to Supabase")
    except Exception as e:
        logger.error(f"Error preprocessing documents: {e}")
        raise
