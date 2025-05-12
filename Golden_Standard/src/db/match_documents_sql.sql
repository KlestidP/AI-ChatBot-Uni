-- Drop the existing functions
DROP FUNCTION IF EXISTS public.match_documents(query_embedding vector, similarity_threshold double precision, match_count integer);
DROP FUNCTION IF EXISTS public.match_documents(query_embedding vector, similarity_threshold double precision, match_count integer, filter jsonb);

-- Create a single function that handles both cases with a default parameter
CREATE OR REPLACE FUNCTION match_documents (
    query_embedding VECTOR(1536),
    similarity_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 5,
    filter JSONB DEFAULT NULL
)
RETURNS TABLE (
    id BIGINT,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF filter IS NULL THEN
        RETURN QUERY
        SELECT
            documents.id::BIGINT,
            documents.content,
            documents.metadata,
            1 - (documents.embedding <=> query_embedding) AS similarity
        FROM documents
        WHERE 1 - (documents.embedding <=> query_embedding) > similarity_threshold
        ORDER BY similarity DESC
        LIMIT match_count;
    ELSE
        RETURN QUERY
        SELECT
            documents.id::BIGINT,
            documents.content,
            documents.metadata,
            1 - (documents.embedding <=> query_embedding) AS similarity
        FROM documents
        WHERE 1 - (documents.embedding <=> query_embedding) > similarity_threshold
        AND documents.metadata @> filter
        ORDER BY similarity DESC
        LIMIT match_count;
    END IF;
END;
$$;