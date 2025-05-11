from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from uni_ai_chatbot.resources import get_resource

_SPLITTER = RecursiveCharacterTextSplitter(
        chunk_size=1_000, chunk_overlap=150, separators=["\n\n", "\n", " "]
)
def load_handbook_docs():
    pdf_path: Path = get_resource(Path("sdt_handbook.pdf"))
    loader = PyPDFLoader(str(pdf_path))
    raw_pages = loader.load()
    for i, doc in enumerate(raw_pages):
        doc.metadata["source"] = "handbook"
        doc.metadata["page_number"] = i + 1
    return _SPLITTER.split_documents(raw_pages)