import logging
from typing import Tuple, Any
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_core.prompts import PromptTemplate
from langchain_mistralai import MistralAIEmbeddings
from langchain_mistralai import ChatMistralAI
from langchain_core.runnables import RunnablePassthrough

from uni_ai_chatbot.configurations.config import MISTRAL_API_KEY, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_RETRIES
from uni_ai_chatbot.utils.database import get_supabase_client
from uni_ai_chatbot.utils.custom_supabase import FixedSupabaseVectorStore

logger = logging.getLogger(__name__)


def get_qa_prompt_template() -> PromptTemplate:
    """Get the QA prompt template with university scope limitation instructions"""
    prompt_template = """You are a helpful university information bot for Constructor University Bremen. Your purpose is to assist students, faculty, and visitors with information about the university.

IMPORTANT: Only answer questions related to Constructor University Bremen, its campus, programs, facilities, procedures, or academic matters. If the question is not directly related to the university, politely explain that you can only discuss university-related topics.

Use the following pieces of context to answer the question at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer.

Context:
{context}

Question: {question}

When answering:
1. Be concise and direct
2. Include relevant details like locations, times, and contact information when available
3. Only discuss university-related matters
4. If the question is not about Constructor University Bremen, politely redirect the user

Answer:
"""
    return PromptTemplate.from_template(prompt_template)


def initialize_qa_chain():
    """Initialize QA chain with Supabase vector store"""
    try:
        # Initialize embeddings
        embeddings = MistralAIEmbeddings(api_key=MISTRAL_API_KEY)

        # Initialize Supabase client
        supabase_client = get_supabase_client()

        # Create vector store
        vector_store = FixedSupabaseVectorStore(
            client=supabase_client,
            embedding=embeddings,
            table_name="documents",
            query_name="match_documents"
        )

        # Initialize LLM
        llm = ChatMistralAI(
            model="mistral-large-latest",
            temperature=0,
            api_key=MISTRAL_API_KEY
        )

        # Create custom prompts
        qa_prompt = get_qa_prompt_template()

        # Create handbook-specific prompt
        handbook_prompt_template = """You are a knowledgeable assistant that specializes in Constructor University program handbooks.
        Use ONLY the following handbook content to answer the question. If the handbook doesn't contain the information, 
        say so clearly, and suggest contacting an academic advisor.

        HANDBOOK CONTENT:
        {context}

        QUESTION: {question}

        Your answer should be detailed and precise, using the exact wording from the handbook when describing requirements.
        Format your response clearly with proper headings and bullet points.
        """

        handbook_prompt = PromptTemplate.from_template(handbook_prompt_template)

        # Create retrievers for different document types
        general_retriever = vector_store.as_retriever(
            search_kwargs={"filter": {}, "k": 6, "score_threshold": 0.5}
        )

        location_retriever = vector_store.as_retriever(
            search_kwargs={"filter": {"metadata": {"tool": "location"}}, "k": 4}
        )

        locker_retriever = vector_store.as_retriever(
            search_kwargs={"filter": {"metadata": {"tool": "locker"}}, "k": 4}
        )

        faq_retriever = vector_store.as_retriever(
            search_kwargs={"filter": {"metadata": {"tool": "qa"}}, "k": 4}
        )

        # Enhanced handbook retriever with improved settings
        handbook_retriever = vector_store.as_retriever(
            # Use standard similarity search instead of MMR
            search_kwargs={
                "filter": {"metadata": {"tool": "handbook"}},
                "k": 10  # Retrieve more documents
            }
        )

        # Create QA chains with custom prompts
        def create_chain(retriever, custom_prompt=None):
            return RetrievalQA.from_chain_type(
                llm=llm,
                retriever=retriever,
                return_source_documents=True,
                chain_type="stuff",
                chain_type_kwargs={"prompt": custom_prompt or qa_prompt}
            )

        # Create specialized QA chains
        general_qa_chain = create_chain(general_retriever)
        location_qa_chain = create_chain(location_retriever)
        locker_qa_chain = create_chain(locker_retriever)
        faq_qa_chain = create_chain(faq_retriever)
        handbook_qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            retriever=handbook_retriever,
            return_source_documents=True,
            chain_type="stuff",
            chain_type_kwargs={"prompt": handbook_prompt}
        )

        return (vector_store, llm, general_qa_chain, location_qa_chain,
                locker_qa_chain, faq_qa_chain, handbook_qa_chain)

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


def initialize_qa_chain_with_provider(provider=None, api_key=None, model=None):
    """Initialize QA chain with specific provider and API key if provided"""
    from uni_ai_chatbot.services.ai_provider_service import get_embeddings_model, get_llm_model
    from uni_ai_chatbot.configurations.config import DEFAULT_PROVIDER, MISTRAL_API_KEY

    try:
        # Get the embeddings model for the specified provider
        embeddings = get_embeddings_model(provider, api_key)

        # Get Supabase client
        supabase_client = get_supabase_client()

        # Create vector store
        vector_store = FixedSupabaseVectorStore(
            client=supabase_client,
            embedding=embeddings,
            table_name="documents",
            query_name="match_documents"
        )

        # Get LLM model
        llm = get_llm_model(provider, api_key, model)

        # Create retrievers for different document types
        general_retriever = vector_store.as_retriever(
            search_kwargs={"filter": {}, "k": 6, "score_threshold": 0.5}
        )

        location_retriever = vector_store.as_retriever(
            search_kwargs={"filter": {"metadata": {"tool": "location"}}, "k": 4}
        )

        locker_retriever = vector_store.as_retriever(
            search_kwargs={"filter": {"metadata": {"tool": "locker"}}, "k": 4}
        )

        faq_retriever = vector_store.as_retriever(
            search_kwargs={"filter": {"metadata": {"tool": "qa"}}, "k": 4}
        )

        handbook_retriever = vector_store.as_retriever(
            search_kwargs={"filter": {"metadata": {"tool": "handbook"}}, "k": 6}
        )

        # Create QA chains for different document types
        general_qa_chain = RetrievalQA.from_chain_type(
            llm=llm, retriever=general_retriever, return_source_documents=True
        )

        location_qa_chain = RetrievalQA.from_chain_type(
            llm=llm, retriever=location_retriever, return_source_documents=True
        )

        locker_qa_chain = RetrievalQA.from_chain_type(
            llm=llm, retriever=locker_retriever, return_source_documents=True
        )

        faq_qa_chain = RetrievalQA.from_chain_type(
            llm=llm, retriever=faq_retriever, return_source_documents=True
        )

        handbook_qa_chain = RetrievalQA.from_chain_type(
            llm=llm, retriever=handbook_retriever, return_source_documents=True
        )

        return (vector_store, llm, general_qa_chain, location_qa_chain,
                locker_qa_chain, faq_qa_chain, handbook_qa_chain)

    except Exception as e:
        logger.error(f"Error initializing QA chain with provider {provider}: {e}")
        # If custom provider fails, fall back to default
        if provider != DEFAULT_PROVIDER:
            logger.info(f"Falling back to {DEFAULT_PROVIDER} provider")
            return initialize_qa_chain_with_provider(DEFAULT_PROVIDER, MISTRAL_API_KEY)
        else:
            # If default provider fails, re-raise the exception
            raise
