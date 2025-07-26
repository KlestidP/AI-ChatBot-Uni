from typing import Dict, List, Any, Optional
from langchain_community.vectorstores.supabase import SupabaseVectorStore
import logging

logger = logging.getLogger(__name__)


class FixedSupabaseVectorStore(SupabaseVectorStore):
    """Custom Supabase vector store that handles UUID primary keys and metadata filtering"""

    def similarity_search_with_relevance_scores(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> List[tuple[Any, float]]:
        """Override to handle metadata filtering properly"""
        embedding = self._embedding.embed_query(query)
        
        # Build the match query
        match_query = {
            "query_embedding": embedding,
            "match_count": k,
        }
        
        # Handle filter for metadata - convert to proper JSONB filter format
        if filter:
            # For Supabase, we need to format the filter for JSONB columns
            # If filter has 'tool' key, we need to filter on metadata->>'tool'
            formatted_filter = {}
            for key, value in filter.items():
                # Convert simple filters to JSONB path filters
                formatted_filter[f"metadata->>'{key}'"] = value
            match_query["filter"] = formatted_filter
            
            logger.debug(f"Applying filter to similarity search: {formatted_filter}")
        
        # Execute the query
        try:
            response = self._client.rpc(self.query_name, match_query).execute()
            
            if hasattr(response, 'data') and response.data:
                logger.debug(f"Found {len(response.data)} documents matching filter")
                # Convert response to expected format
                results = []
                for item in response.data:
                    doc = self._document_from_result(item)
                    score = item.get('similarity', 0.0)
                    results.append((doc, score))
                return results
            else:
                logger.warning("No documents found with the given filter")
                return []
                
        except Exception as e:
            logger.error(f"Error in similarity search: {e}")
            # Fall back to base implementation without filter
            if filter:
                logger.warning("Falling back to search without filter due to error")
                return super().similarity_search_with_relevance_scores(query, k, **kwargs)
            raise

    def _get_match_documents_query(
            self, query_embedding: List[float], filter: Optional[Dict[str, Any]] = None, limit: int = 5
    ) -> Dict[str, Any]:
        """
        Override the match documents query to ensure proper UUID and filter handling
        """
        match_query = {
            "query_embedding": query_embedding,
            "match_count": limit,
        }

        if filter is not None:
            # Handle metadata filtering for JSONB columns
            formatted_filter = {}
            for key, value in filter.items():
                # For metadata JSONB column, use proper PostgreSQL syntax
                formatted_filter[f"metadata->>'{key}'"] = value
            match_query["filter"] = formatted_filter
            logger.debug(f"Match documents query with filter: {formatted_filter}")

        return match_query
    
    def _document_from_result(self, result: Dict[str, Any]) -> Any:
        """Convert a result from Supabase to a Document object"""
        from langchain_core.documents import Document
        
        return Document(
            page_content=result.get("content", ""),
            metadata=result.get("metadata", {})
        )