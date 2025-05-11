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
        
        # Create vector store
        vector_store = SupabaseVectorStore(
            client=supabase_client,
            embedding=embeddings,
            table_name="documents",
            query_name="match_documents"
        )
        
        # Get retriever
        retriever = vector_store.as_retriever(
            search_kwargs={"k": 4}  # Get top 4 most relevant documents
        )

        # Initialize the language model
        llm = ChatMistralAI(
            model="mistral-large-latest",
            temperature=0,
            max_retries=2,
            api_key=MISTRAL_API_KEY
        )

        logger.info("Successfully initialized QA chain with Supabase vector store")
        return RetrievalQA.from_chain_type(
            llm=llm, 
            retriever=retriever,
            return_source_documents=True  # This will return the source documents used to generate the answer
        )

    except Exception as e:
        logger.error(f"Error initializing QA chain: {e}")
        raise