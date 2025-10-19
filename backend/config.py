import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Configuration management for the RAG application"""
    
    # API Keys
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    NOTION_TOKEN: Optional[str] = os.getenv("NOTION_TOKEN")
    
    # Database Configuration
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "podcast_chunks")
    
    # Model Configuration
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    
    # Search Configuration
    DEFAULT_SEARCH_LIMIT: int = int(os.getenv("DEFAULT_SEARCH_LIMIT", "5"))
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
    
    # Server Configuration
    HOST: str = os.getenv("HOST", "localhost")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    @classmethod
    def validate(cls) -> bool:
        """Validate that required configuration is present"""
        required_keys = ["OPENAI_API_KEY"]
        missing_keys = [key for key in required_keys if not getattr(cls, key)]
        
        if missing_keys:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_keys)}")
        
        return True

# Global config instance
config = Config()