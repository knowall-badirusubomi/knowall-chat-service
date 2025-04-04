import os
import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

import google.generativeai as genai
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter



@dataclass
class Conversation:
    messages: List[Dict[str, str]] = field(default_factory=list)
    max_history: int = 5
    
    def add_message(self, role: str, content: str):
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        # Keep only the last max_history messages
        if len(self.messages) > self.max_history:
            self.messages = self.messages[-self.max_history:]
    
    def get_context(self) -> str:
        return "\n".join([
            f"{msg['role']}: {msg['content']}" 
            for msg in self.messages
        ])

@dataclass
class UserSession:
    user_id: str
    conversation: 'Conversation'
    last_active: datetime = field(default_factory=datetime.now)

class SessionManager:
    def __init__(self, session_timeout_minutes: int = 30):
        self.sessions: Dict[str, UserSession] = {}
        self.session_timeout = session_timeout_minutes
        
    def create_session(self) -> str:
        """Create a new user session and return session ID"""
        session_id = str(uuid4())
        self.sessions[session_id] = UserSession(
            user_id=session_id,
            conversation=Conversation()
        )
        return session_id
    
    def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get session by ID and update last active time"""
        session = self.sessions.get(session_id)
        if session:
            session.last_active = datetime.now()
        return session
    
    def cleanup_inactive_sessions(self):
        """Remove inactive sessions"""
        current_time = datetime.now()
        inactive_sessions = [
            sid for sid, session in self.sessions.items()
            if (current_time - session.last_active).total_seconds() > (self.session_timeout * 60)
        ]
        for sid in inactive_sessions:
            del self.sessions[sid]

class RAGEngine:
    def __init__(self):
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=GOOGLE_API_KEY
        )
        self.vector_store = None
        self.model = genai.GenerativeModel('gemini-pro')
        self.session_manager = SessionManager()
        
    def load_documents(self, docs_path: str = "ercaspay_docs") -> List[Dict]:
        """Load and process documents from the specified directory"""
        documents = []
        docs_dir = Path(docs_path)
        
        # Add debug logging
        print(f"Looking for documents in: {docs_dir.absolute()}")
        
        if not docs_dir.exists():
            raise ValueError(f"Directory {docs_dir.absolute()} does not exist")
        
        # Process JSON files
        for json_file in docs_dir.glob("*.json"):
            print(f"Processing JSON file: {json_file}")
            with open(json_file, 'r') as f:
                content = json.load(f)
                doc_text = json.dumps(content, indent=2)
                documents.append({
                    "content": doc_text,
                    "source": str(json_file)
                })
        
        # Process text files
        for txt_file in docs_dir.glob("*.txt"):
            print(f"Processing text file: {txt_file}")
            with open(txt_file, 'r') as f:
                content = f.read()
                documents.append({
                    "content": content,
                    "source": str(txt_file)
                })
        
        if not documents:
            raise ValueError("No documents found in the specified directory")
        
        print(f"Loaded {len(documents)} documents")
        return documents
    
    def create_vector_store(self, documents: List[Dict]):
        """Create vector store from documents using ChromaDB"""
        # Split documents into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        
        texts = []
        metadatas = []
        
        for doc in documents:
            chunks = text_splitter.split_text(doc["content"])
            texts.extend(chunks)
            metadatas.extend([{"source": doc["source"]} for _ in chunks])
        
        # Create vector store using Chroma instead of FAISS
        self.vector_store = Chroma.from_texts(
            texts,
            self.embeddings,
            metadatas=metadatas,
            persist_directory="./chroma_db"  # This will persist the database
        )
    
    def query(self, question: str, session_id: str = None, k: int = 3) -> tuple[str, str]:
        """Query the RAG system with session awareness"""
        if not self.vector_store:
            raise ValueError("Vector store not initialized. Please load documents first.")
        
        # Create or get session
        if not session_id:
            session_id = self.session_manager.create_session()
        
        session = self.session_manager.get_session(session_id)
        if not session:
            session_id = self.session_manager.create_session()
            session = self.session_manager.get_session(session_id)
        
        # Clean up old sessions periodically
        self.session_manager.cleanup_inactive_sessions()
        
        # Add user question to conversation history
        session.conversation.add_message("user", question)
        
        # Retrieve relevant documents
        relevant_docs = self.vector_store.similarity_search(question, k=k)
        
        # Get conversation history
        conversation_context = session.conversation.get_context()
        
        # Construct prompt with context and conversation history
        doc_context = "\n\n".join([doc.page_content for doc in relevant_docs])
        prompt = f"""Based on the following documentation and conversation history:

Documentation Context:
{doc_context}

User Session: {session_id}
Conversation History:
{conversation_context}

Current Question: {question}

Please provide a detailed answer that:
1. If the question is a greeting or general query, respond appropriately as an Ercaspay Support Assistant
2. For technical questions, use only the information from the documentation above
3. Maintains context from the previous conversation for this specific user
4. Addresses the current question directly
5. If referring to previous context, explicitly mentions what you're referring to

Answer:"""

        # Generate response using Gemini
        response = self.model.generate_content(prompt)
        
        # Add assistant's response to conversation history
        session.conversation.add_message("assistant", response.text)
        
        return response.text, session_id
    
    def reset_session(self, session_id: str) -> bool:
        """Reset a specific user session"""
        session = self.session_manager.get_session(session_id)
        if session:
            session.conversation = Conversation()
            return True
        return False

def main():
    
    # Initialize RAG system
    rag = RAGEngine()
    
    # Load and process documents
    print("Loading and processing documents...")
    documents = rag.load_documents(r"C:\Users\adele\Ercaspay-Hackathon\ercaspay_docs")
    rag.create_vector_store(documents)
    
    print("\nErcaspay Support Assistant Ready! (Type 'quit' to exit, 'reset' to start a new conversation)")
    
    current_session_id = None
    
    # Example usage
    while True:
        question = input("\nYou: ").strip()
        
        if question.lower() == 'quit':
            break
        elif question.lower() == 'reset':
            if current_session_id:
                rag.reset_session(current_session_id)
                print("\nConversation reset. Starting new conversation.")
            continue
            
        try:
            answer, session_id = rag.query(question, current_session_id)
            current_session_id = session_id
            print("\nAssistant:", answer)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":

    # Retrieving the value of the "GOOGLE_API_KEY" environment variable
    try:
        GOOGLE_API_KEY = os.environ["GOOGLE_API_KEY"]
    except Exception as e:
        raise SystemError('Google API KEY not specified')


    print(GOOGLE_API_KEY)
    # Configure Gemini API
    # genai.configure(api_key=GOOGLE_API_KEY)
    # main() 