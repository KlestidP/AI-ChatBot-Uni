-- This is the SQL script to create the match_documents function in Supabase
-- Copy this script and run it in the Supabase SQL Editor

-- Enable the pgvector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- First, create the documents table if it doesn't exist
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB,
    embedding VECTOR(1536)
);

-- Create search function using cosine similarity
CREATE OR REPLACE FUNCTION match_documents (
    query_embedding VECTOR(1536),
    similarity_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 5
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
END;
$$;

-- Create an index for faster similarity search
CREATE INDEX IF NOT EXISTS documents_embedding_idx ON documents
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Notify success
DO $$
BEGIN
    RAISE NOTICE 'Successfully created match_documents function and necessary database objects';
END $$;