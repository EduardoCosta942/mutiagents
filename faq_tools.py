import os
from dotenv import load_dotenv
from langchain.tools import tool
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

PDF_PATH = os.getenv("FAQ_PDF_PATH", "faq.pdf")
loader = PyPDFLoader(PDF_PATH)
docs = loader.load()

@tool("faq_retriever")
def faq_retriever(question: str) -> str:
    """
    Retrieve relevant information from the FAQ document based on the user's question.
    Args:
        question (str): The user's question.
    Returns:
        str: The relevant information from the FAQ document.
    """
    global docs
    # Split the document into smaller chunks
    chunks = RecursiveCharacterTextSplitter(chunk_size=760, chunk_overlap=150
                        ).split_documents(docs)
    
    # Converting chuck to vectorstore
    embeddings = GoogleGenerativeAIEmbeddings(
        model = "gemini-embedding-2-preview",
        google_api_key=os.getenv("GEMINI_API_KEY")
    )

    # Create a FAISS vector store from the document chunks
    db = FAISS.from_documents(chunks, embeddings)

    return db.similarity_search(question, k=6)