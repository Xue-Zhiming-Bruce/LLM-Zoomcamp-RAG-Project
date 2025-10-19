import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
from config import config
import requests

logger = logging.getLogger(__name__)

class RAGService:
    """RAG (Retrieval-Augmented Generation) service for podcast content"""
    
    def __init__(self):
        """Initialize the RAG service with all required components"""
        self.qdrant_client = None
        self.embedding_model = None
        self.llm_client = None
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize all external service clients"""
        try:
            # Initialize Qdrant client
            self.qdrant_client = QdrantClient(
                host=config.QDRANT_HOST, 
                port=config.QDRANT_PORT
            )
            logger.info(f"Connected to Qdrant at {config.QDRANT_HOST}:{config.QDRANT_PORT}")
            
            # Initialize embedding model lazily
            self.embedding_model = None
            logger.info(f"Embedding model deferred: {config.EMBEDDING_MODEL}")
            
            # Defer OpenAI client initialization
            self.llm_client = None
            logger.info("OpenAI client deferred")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {e}")
            raise

    def _ensure_embedding_model(self):
        if self.embedding_model is None:
            self.embedding_model = SentenceTransformer(config.EMBEDDING_MODEL)
            logger.info(f"Loaded embedding model: {config.EMBEDDING_MODEL}")
        return self.embedding_model

    def _ensure_llm_client(self):
        if self.llm_client is None:
            try:
                self.llm_client = OpenAI()
                logger.info("Initialized OpenAI client")
            except Exception as e:
                logger.error(f"OpenAI client init failed: {e}")
                self.llm_client = None
        return self.llm_client

    def search_similar_content(self, query: str, limit: int = None) -> List[Dict[str, Any]]:
        """
        Search for similar content using vector similarity
        
        Args:
            query: The search query
            limit: Maximum number of results to return
            
        Returns:
            List of similar content chunks with metadata
        """
        if limit is None:
            limit = config.DEFAULT_SEARCH_LIMIT
            
        try:
            # Generate query embedding
            query_vector = self._ensure_embedding_model().encode(query).tolist()
            
            # Search in Qdrant
            search_result = self.qdrant_client.search(
                collection_name=config.COLLECTION_NAME,
                query_vector=query_vector,
                limit=limit
            )
            
            # Format results (normalize payloads)
            results = []
            for scored_point in search_result:
                payload = scored_point.payload or {}
                tag_value = payload.get("podcast_tag", "")
                if isinstance(tag_value, list):
                    # Normalize list payloads to a readable string
                    tag_value = ", ".join(str(t) for t in tag_value if t is not None)
                results.append({
                    "id": scored_point.id,
                    "score": scored_point.score,
                    "podcast_tag": tag_value,
                    "podcast_title": payload.get("podcast_title", ""),
                    "content": payload.get("content", "")
                })
            
            logger.info(f"Found {len(results)} similar content chunks for query: {query[:50]}...")
            return results
            
        except Exception as e:
            logger.error(f"Error searching similar content: {e}")
            raise

    def generate_rag_prompt(self, query: str, search_results: List[Dict[str, Any]]) -> str:
        """
        Generate a prompt for the LLM using the query and search results
        
        Args:
            query: The user's question
            search_results: List of relevant content chunks
            
        Returns:
            Formatted prompt for the LLM
        """
        template = """You are an AI assistant helping users understand podcast content. Use the provided context to answer the user's question accurately and comprehensively.

Context from podcast transcripts:
{context}

User Question: {query}

Instructions:
- Base your answer primarily on the provided context
- If the context doesn't contain enough information, clearly state this
- Provide a comprehensive and helpful answer
- If the context is in Chinese, you can respond in both Chinese and English as appropriate
- Be conversational and engaging

Answer:"""

        # Build context from search results
        context = ""
        for i, result in enumerate(search_results, 1):
            context += f"[Source {i}] Title: '{result['podcast_title']}', Tag: '{result['podcast_tag']}'\n"
            context += f"Content: {result['content']}\n\n"

        prompt = template.format(query=query, context=context.strip())
        return prompt

    def generate_answer(self, query: str, search_results: List[Dict[str, Any]]) -> str:
        """
        Generate an answer using the LLM based on the query and search results
        
        Args:
            query: The user's question
            search_results: List of relevant content chunks
            
        Returns:
            Generated answer from the LLM
        """
        try:
            prompt = self.generate_rag_prompt(query, search_results)
            
            # Prefer SDK if available
            client = self._ensure_llm_client()
            if client:
                response = client.chat.completions.create(
                    model=config.LLM_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a helpful AI assistant that answers questions based on podcast content."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1000,
                    temperature=0.7
                )
                answer = response.choices[0].message.content
                logger.info(f"Generated answer for query: {query[:50]}...")
                return answer
            
            # Fallback: direct HTTP call to OpenAI API
            headers = {
                "Authorization": f"Bearer {config.OPENAI_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": config.LLM_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a helpful AI assistant that answers questions based on podcast content."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1000,
                "temperature": 0.7
            }
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            resp.raise_for_status()
            answer = resp.json()["choices"][0]["message"]["content"]
            logger.info(f"Generated answer via HTTP fallback for query: {query[:50]}...")
            return answer
            
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            raise

    def chat(self, query: str, limit: int = None) -> Dict[str, Any]:
        """
        Complete RAG pipeline: search + generate answer
        
        Args:
            query: The user's question
            limit: Maximum number of search results to use
            
        Returns:
            Dictionary containing the answer and metadata
        """
        try:
            # Search for relevant content
            search_results = self.search_similar_content(query, limit)
            
            if not search_results:
                return {
                    "answer": "I couldn't find any relevant content to answer your question. Please try rephrasing your question or asking about a different topic.",
                    "sources": [],
                    "query": query
                }
            
            # Generate answer
            answer = self.generate_answer(query, search_results)
            
            # Format sources for frontend
            sources = [
                {
                    "title": result["podcast_title"],
                    "tag": result["podcast_tag"],
                    "score": round(result["score"], 3),
                    "content_preview": result["content"][:200] + "..." if len(result["content"]) > 200 else result["content"]
                }
                for result in search_results
            ]
            
            return {
                "answer": answer,
                "sources": sources,
                "query": query
            }
            
        except Exception as e:
            logger.error(f"Error in chat pipeline: {e}")
            raise

    def health_check(self) -> Dict[str, Any]:
        """
        Check the health of all service components
        
        Returns:
            Dictionary with health status of each component
        """
        health_status = {
            "status": "healthy",
            "components": {}
        }
        
        try:
            # Check Qdrant connection
            collections = self.qdrant_client.get_collections()
            collection_names = [col.name for col in collections.collections]
            health_status["components"]["qdrant"] = {
                "status": "healthy",
                "collections": collection_names,
                "target_collection_exists": config.COLLECTION_NAME in collection_names
            }
        except Exception as e:
            health_status["components"]["qdrant"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_status["status"] = "unhealthy"
        
        # Embedding model status (lazy-loaded)
        if self.embedding_model is None:
            health_status["components"]["embedding_model"] = {
                "status": "deferred",
                "model": config.EMBEDDING_MODEL
            }
        else:
            health_status["components"]["embedding_model"] = {
                "status": "initialized",
                "model": config.EMBEDDING_MODEL
            }
        
        # OpenAI client status (lazy-loaded)
        if self.llm_client is None:
            health_status["components"]["openai"] = {
                "status": "deferred",
                "model": config.LLM_MODEL
            }
        else:
            health_status["components"]["openai"] = {
                "status": "initialized",
                "model": config.LLM_MODEL
            }
        
        return health_status