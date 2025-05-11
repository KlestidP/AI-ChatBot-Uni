# Use Python 3.11 as base image
FROM python:3.11

# Set working directory
WORKDIR /app

# Install required system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary (from official image) into this image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY --from=ghcr.io/astral-sh/uv:latest /uvx /bin/uvx

# Copy requirements file first to leverage Docker cache
COPY uv.lock pyproject.toml README.md ./

# Install Python dependencies
RUN uv sync --no-install-package uni_ai_chatbot

# Copy application code
COPY src ./src

RUN mkdir -p /app/uni_ai_chatbot/data/vectorstore


RUN uv sync

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Set the default command (this will be overridden by docker-compose)
ENTRYPOINT ["/docker-entrypoint.sh"]