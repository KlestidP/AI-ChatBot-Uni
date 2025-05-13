import logging
from typing import Tuple, Any
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_mistralai import MistralAIEmbeddings
from langchain_mistralai import ChatMistralAI

from uni_ai_chatbot.configurations.config import MISTRAL_API_KEY, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_RETRIES
from uni_ai_chatbot.utils.database import get_supabase_client

logger = logging.getLogger(__name__)


def initialize_qa_chain() -> Tuple[Any, ChatMistralAI, Any, Any, Any, Any]:
    """
    Initialize the QA chain using Supabase vector store

    Returns:
        Tuple containing:
        - vector_store: The Supabase vector store
        - llm: The language model
        - general_qa_chain: Chain that can access all data
        - location_qa_chain: Chain for location data
        - locker_qa_chain: Chain for locker data
        - faq_qa_chain: Chain for FAQ data

    Raises:
        ValueError: If required environment variables are not set
    """
    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY is not set in environment variables")

    try:
        logger.info("Initializing QA chain with Supabase vector store")

        # Set up embeddings
        embeddings = MistralAIEmbeddings(api_key=MISTRAL_API_KEY)

        # Create Supabase client
        supabase_client = get_supabase_client()

        # Create the base vector store
        vector_store = SupabaseVectorStore(
            client=supabase_client,
            embedding=embeddings,
            table_name="documents",
            query_name="match_documents"
        )

        # Initialize the language model
        llm = ChatMistralAI(
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            max_retries=LLM_MAX_RETRIES,
            api_key=MISTRAL_API_KEY
        )

        # Create specialized QA chains for different tool types
        location_qa_chain = get_scoped_qa_chain(vector_store, llm, "location")
        locker_qa_chain = get_scoped_qa_chain(vector_store, llm, "locker")
        faq_qa_chain = get_scoped_qa_chain(vector_store, llm, "qa")  # Use "qa" type for FAQs

        # Create the base QA chain with the ability to access all data
        general_qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            retriever=vector_store.as_retriever(search_kwargs={"k": 4}),
            return_source_documents=True
        )

        logger.info("Successfully initialized QA chains")
        return vector_store, llm, general_qa_chain, location_qa_chain, locker_qa_chain, faq_qa_chain

    except Exception as e:
        logger.error(f"Error initializing QA chain: {e}")
        raise


def get_scoped_qa_chain(vector_store: SupabaseVectorStore, llm: ChatMistralAI, tool_type: str) -> RetrievalQA:
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