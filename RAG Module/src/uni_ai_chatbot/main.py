import os
from pathlib import Path
from langchain.chains import RetrievalQA
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import CharacterTextSplitter
from langchain_mistralai import MistralAIEmbeddings
from langchain_mistralai import ChatMistralAI


from uni_ai_chatbot.resources import get_resource

# Load API key from env (make sure it's set)
mistral_api_key = os.environ.get("MISTRAL_API_KEY")
if not mistral_api_key:
    raise ValueError("MISTRAL_API_KEY is not set in environment variables")

# Load and split text
file_path = get_resource(relative_path=Path("data.txt"))
loader = TextLoader(file_path)
documents = loader.load()

text_splitter = CharacterTextSplitter(chunk_size=200, chunk_overlap=20)
split_docs = text_splitter.split_documents(documents)
texts = [doc.page_content for doc in split_docs]

# Use Mistral embeddings (ensure the Mistral API and embeddings functionality is available)
embeddings = MistralAIEmbeddings(api_key=mistral_api_key)
vector_store = FAISS.from_texts(texts, embeddings)
retriever = vector_store.as_retriever()

# Use ChatMistralAI for LLM
llm = ChatMistralAI(
    model="mistral-large-latest",
    temperature=0,
    max_retries=2
)

# Build QA chain
qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=retriever)


# CLI
def run_queries():
    queries = []
    print("Enter your queries (type 'done' to finish):")
    while True:
        query = input("> ")
        if query.lower() == "done":
            break
        queries.append(query)

    for query in queries:
        print(f"\nQuery: {query}")
        response = qa_chain.invoke(query)
        print(f"Response: {response['result']}")


if __name__ == "__main__":
    run_queries()
