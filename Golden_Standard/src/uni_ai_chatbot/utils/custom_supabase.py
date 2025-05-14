from typing import Dict, List, Any, Optional
from langchain_community.vectorstores.supabase import SupabaseVectorStore


class FixedSupabaseVectorStore(SupabaseVectorStore):
    """Custom Supabase vector store that handles UUID primary keys"""

    def _get_match_documents_query(
            self, query_embedding: List[float], filter: Optional[Dict[str, Any]] = None, limit: int = 5
    ) -> Dict[str, Any]:
        """
        Override the match documents query to ensure proper UUID handling
        """
        match_query = {
            "query_embedding": query_embedding,
            "match_count": limit,
        }

        if filter is not None:
            match_query["filter"] = filter

        return match_query