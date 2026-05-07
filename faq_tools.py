import os
from dotenv import load_dotenv
from langchain.tools import tool
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

# Initialize resources once at module load
PDF_PATH = os.getenv("FAQ_PDF_PATH", "faq.pdf")
loader = PyPDFLoader(PDF_PATH)
docs = loader.load()

# Split documents once
text_splitter = RecursiveCharacterTextSplitter(chunk_size=760, chunk_overlap=150)
chunks = text_splitter.split_documents(docs)

# Initialize embeddings once
embeddings = GoogleGenerativeAIEmbeddings(
    model="gemini-embedding-2-preview",
    google_api_key=os.getenv("GEMINI_API_KEY")
)

# Create vector store once
db = FAISS.from_documents(chunks, embeddings)

@tool("faq_retriever")
def faq_retriever(question: str) -> str:
    """
    Retrieve relevant information from the FAQ document based on the user's question.
    Args:
        question (str): The user's question.
    Returns:
        str: The relevant information from the FAQ document.
    """
    print("Retrieving information from the FAQ document...")
    consult = db.similarity_search(question, k=6)
    return "\n".join([doc.page_content for doc in consult])