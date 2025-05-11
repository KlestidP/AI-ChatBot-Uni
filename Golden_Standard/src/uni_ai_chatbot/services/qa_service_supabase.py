import os
import logging
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_mistralai import MistralAIEmbeddings
from langchain_mistralai import ChatMistralAI
from supabase import create_client

logger = logging.getLogger(__name__)


def initialize_qa_chain():
    """Initialize the QA chain using Supabase vector store"""
    MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY is not set in environment variables")
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Supabase credentials not found in environment variables")

    try:
        logger.info("Initializing QA chain with Supabase vector store")

        # Set up embeddings
        embeddings = MistralAIEmbeddings(api_key=MISTRAL_API_KEY)

        # Create Supabase client
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

        # Create the base vector store
        vector_store = SupabaseVectorStore(
            client=supabase_client,
            embedding=embeddings,
            table_name="documents",
            query_name="match_documents"
        )

        # Initialize the language model
        llm = ChatMistralAI(
            model="mistral-large-latest",
            temperature=0,
            max_retries=2,
            api_key=MISTRAL_API_KEY
        )

        # Create the base QA chain with the ability to access all data
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            retriever=vector_store.as_retriever(search_kwargs={"k": 4}),
            return_source_documents=True
        )

        logger.info("Successfully initialized QA chain with Supabase vector store")
        return vector_store, llm, qa_chain

    except Exception as e:
        logger.error(f"Error initializing QA chain: {e}")
        raise


def get_scoped_qa_chain(vector_store, llm, tool_type):
    """
    Get a QA chain that only retrieves documents relevant to a specific tool

    Args:
        vector_store: The base vector store to create a filtered retriever from
        llm: The language model to use
        tool_type: The tool type to filter documents by ('qa', 'location', or 'locker')

    Returns:
        A QA chain that only queries documents of the specified tool type
    """
    # Create a filtered retriever that only returns documents of the specified tool type
    retriever = vector_store.as_retriever(
        search_kwargs={
            "k": 4,
            "filter": {"tool": tool_type}
        }
    )

    # Create a QA chain with the filtered retriever
    return RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        return_source_documents=True
    )