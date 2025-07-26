import logging
from typing import Tuple, Any, List, Dict
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_core.prompts import PromptTemplate
from langchain_mistralai import MistralAIEmbeddings
from langchain_mistralai import ChatMistralAI
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun

from uni_ai_chatbot.configurations.config import MISTRAL_API_KEY, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_RETRIES
from uni_ai_chatbot.utils.database import get_supabase_client
from uni_ai_chatbot.utils.custom_supabase import FixedSupabaseVectorStore

logger = logging.getLogger(__name__)


class FilteredRetriever(BaseRetriever):
    """A custom retriever that filters documents by metadata after retrieval"""
    
    base_retriever: BaseRetriever
    filter_dict: Dict[str, Any]
    k: int = 4
    
    class Config:
        """Configuration for this pydantic object."""
        arbitrary_types_allowed = True
    
    def _get_relevant_documents(
        self, 
        query: str, 
        *, 
        run_manager: CallbackManagerForRetrieverRun = None
    ) -> List[Document]:
        """Retrieve documents and filter by metadata"""
        # Get more documents than needed (k * 3) using invoke method
        all_docs = self.base_retriever.invoke(query)
        
        # Filter documents based on metadata
        filtered_docs = []
        for doc in all_docs:
            match = True
            for key, value in self.filter_dict.items():
                if doc.metadata.get(key) != value:
                    match = False
                    break
            if match:
                filtered_docs.append(doc)
        
        # Return up to k documents
        logger.debug(f"Filtered {len(filtered_docs)} docs from {len(all_docs)} total")
        return filtered_docs[:self.k]


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

        # Create a handbook-specific prompt
        handbook_prompt_template = """You are a knowledgeable assistant that specializes in Constructor University program handbooks.

                Use the following handbook content to answer the question. Be thorough and specific in your response.

                IMPORTANT: 
                - If the provided context doesn't contain enough information to fully answer the question, say what you can based on the available information and mention what specific information is missing.
                - For simple factual questions (like names, dates, or single facts), provide a clear, direct answer.
                - For complex questions requiring explanation, use structured formatting with headings and bullet points.

                Context from handbooks:
                {context}

                Question: {question}

                Guidelines for your response:
                - For simple questions: Provide a direct, concise answer with relevant details (e.g., course codes, titles)
                - For complex questions: Include the following where applicable:
                  • Specific requirements or criteria mentioned
                  • Credit hours or ECTS if mentioned
                  • Any important policies or procedures
                  • Relevant deadlines or timelines
                  • Professor names and contact info if asked

                Always format your response appropriately for the question's complexity.
                """

        handbook_prompt = PromptTemplate.from_template(handbook_prompt_template)

        # Create base retriever that gets more documents
        base_retriever = vector_store.as_retriever(
            search_kwargs={"k": 20}  # Get more documents for filtering
        )

        # Create filtered retrievers using our custom FilteredRetriever
        general_retriever = vector_store.as_retriever(
            search_kwargs={"k": 6}
        )

        location_retriever = FilteredRetriever(
            base_retriever=base_retriever,
            filter_dict={"tool": "location"},
            k=4
        )

        locker_retriever = FilteredRetriever(
            base_retriever=base_retriever,
            filter_dict={"tool": "locker"},
            k=4
        )

        faq_retriever = FilteredRetriever(
            base_retriever=base_retriever,
            filter_dict={"tool": "qa"},
            k=4
        )

        # Special handling for handbook retriever - get more docs
        handbook_retriever = FilteredRetriever(
            base_retriever=base_retriever,
            filter_dict={"tool": "handbook"},
            k=15  # Get more handbook chunks for better context
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
        
        # Special handbook chain with enhanced prompt
        handbook_qa_chain = create_chain(handbook_retriever, handbook_prompt)

        # Log initialization success
        logger.info("Successfully initialized all QA chains with filtered retrievers")

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
    # Create base retriever
    base_retriever = vector_store.as_retriever(
        search_kwargs={"k": 20}
    )
    
    # Create a filtered retriever
    filtered_retriever = FilteredRetriever(
        base_retriever=base_retriever,
        filter_dict={"tool": tool_type},
        k=4
    )

    # Create a QA chain with the filtered retriever
    return RetrievalQA.from_chain_type(
        llm=llm,
        retriever=filtered_retriever,
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

        # Create custom prompts
        qa_prompt = get_qa_prompt_template()
        
        handbook_prompt_template = """You are a knowledgeable assistant that specializes in Constructor University program handbooks.
        
        Use the following handbook content to answer the question. Be thorough and specific in your response.
        
        IMPORTANT: If the provided context doesn't contain enough information to fully answer the question, 
        say what you can based on the available information and mention what specific information is missing.

        Context from handbooks:
        {context}

        Question: {question}

        Provide a detailed answer using the handbook information. Include:
        - Specific requirements or criteria mentioned
        - Credit hours or ECTS if mentioned
        - Any important policies or procedures
        - Relevant deadlines or timelines
        
        Format your response clearly with bullet points where appropriate.
        """

        handbook_prompt = PromptTemplate.from_template(handbook_prompt_template)

        # Create base retriever
        base_retriever = vector_store.as_retriever(
            search_kwargs={"k": 20}
        )

        # Create filtered retrievers
        general_retriever = vector_store.as_retriever(
            search_kwargs={"k": 6}
        )

        location_retriever = FilteredRetriever(
            base_retriever=base_retriever,
            filter_dict={"tool": "location"},
            k=4
        )

        locker_retriever = FilteredRetriever(
            base_retriever=base_retriever,
            filter_dict={"tool": "locker"},
            k=4
        )

        faq_retriever = FilteredRetriever(
            base_retriever=base_retriever,
            filter_dict={"tool": "qa"},
            k=4
        )

        handbook_retriever = FilteredRetriever(
            base_retriever=base_retriever,
            filter_dict={"tool": "handbook"},
            k=15
        )

        # Create QA chains for different document types
        general_qa_chain = RetrievalQA.from_chain_type(
            llm=llm, 
            retriever=general_retriever, 
            return_source_documents=True,
            chain_type_kwargs={"prompt": qa_prompt}
        )

        location_qa_chain = RetrievalQA.from_chain_type(
            llm=llm, 
            retriever=location_retriever, 
            return_source_documents=True,
            chain_type_kwargs={"prompt": qa_prompt}
        )

        locker_qa_chain = RetrievalQA.from_chain_type(
            llm=llm, 
            retriever=locker_retriever, 
            return_source_documents=True,
            chain_type_kwargs={"prompt": qa_prompt}
        )

        faq_qa_chain = RetrievalQA.from_chain_type(
            llm=llm, 
            retriever=faq_retriever, 
            return_source_documents=True,
            chain_type_kwargs={"prompt": qa_prompt}
        )

        handbook_qa_chain = RetrievalQA.from_chain_type(
            llm=llm, 
            retriever=handbook_retriever, 
            return_source_documents=True,
            chain_type_kwargs={"prompt": handbook_prompt}
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