import os
from pathlib import Path
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import FAISS
from langchain_mistralai import MistralAIEmbeddings
from langchain_mistralai import ChatMistralAI
from uni_ai_chatbot.scripts.preprocess_documents import get_index_path
import logging

logger = logging.getLogger(__name__)



def initialize_qa_chain():
    """Initialize the QA chain using a pre-built vector store"""
    MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")

    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY is not set in environment variables")

    # Path to the persisted FAISS index
    index_path = get_index_path()

    # Check if index exists
    if not Path(index_path).exists():
        raise FileNotFoundError(
            f"FAISS index not found at {index_path}. "
            "Please run the preprocessing script first."
        )

    try:
        logger.info(f"Loading FAISS index from {index_path}")
        embeddings = MistralAIEmbeddings(api_key=MISTRAL_API_KEY)
        vector_store = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
        retriever = vector_store.as_retriever()

        llm = ChatMistralAI(
            model="mistral-large-latest",
            temperature=0,
            max_retries=2,
            api_key=MISTRAL_API_KEY
        )

        logger.info("Successfully loaded FAISS index and initialized QA chain")
        return RetrievalQA.from_chain_type(llm=llm, retriever=retriever)

    except Exception as e:
        logger.error(f"Error initializing QA chain: {e}")
        raise