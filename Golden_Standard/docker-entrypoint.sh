#!/bin/bash
set -e

echo "🚀 Starting Uni AI Chatbot..."

# Check if the FAISS index file exists
if [ ! -f /app/src/uni_ai_chatbot/data/vectorstore/index.faiss ]; then
    echo "⚠️ FAISS index not found. Running preprocessing script..."
    python /app/src/uni_ai_chatbot/scripts/preprocess_documents.py
    echo "✅ Preprocessing completed."
else
    echo "✅ FAISS index found. Skipping preprocessing."
fi

# Run the main container command
exec "$@"