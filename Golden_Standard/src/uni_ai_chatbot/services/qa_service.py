import os
from pathlib import Path
from langchain.chains import RetrievalQA
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_mistralai import MistralAIEmbeddings
from langchain_mistralai import ChatMistralAI
from uni_ai_chatbot.data.resources import load_faq_answers
from uni_ai_chatbot.data.campus_map_data import load_campus_map


def get_resource(relative_path):
    # Helper function to handle resource paths
    base_dir = Path(__file__).parent.parent
    return str(base_dir / relative_path)


def initialize_qa_chain():
    # Create documents directly from database content
    documents = []
    MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")

    # Add FAQ data as documents
    faq_data = load_faq_answers()
    for question, answer in faq_data.items():
        doc_content = f"Question: {question}\nAnswer: {answer}"
        documents.append(Document(page_content=doc_content))

    # Add campus location data as documents
    campus_data = load_campus_map()
    for location in campus_data:
        doc_content = f"Location: {location['name']}\n"

        if location.get('tags'):
            doc_content += f"Features: {location['tags']}\n"

        if location.get('aliases'):
            doc_content += f"Also known as: {location['aliases']}\n"

        doc_content += f"Address: {location.get('address', 'Unknown')}"
        documents.append(Document(page_content=doc_content))

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=200,
        chunk_overlap=20,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    split_docs = text_splitter.split_documents(documents)
    embeddings = MistralAIEmbeddings(api_key=MISTRAL_API_KEY)
    vector_store = FAISS.from_texts([doc.page_content for doc in split_docs], embeddings)
    retriever = vector_store.as_retriever()
    llm = ChatMistralAI(
        model="mistral-large-latest",
        temperature=0,
        max_retries=2,
        api_key=MISTRAL_API_KEY
    )
    return RetrievalQA.from_chain_type(llm=llm, retriever=retriever)
