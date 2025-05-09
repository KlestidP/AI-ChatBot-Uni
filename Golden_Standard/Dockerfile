# Use Python 3.11 as base image
FROM python:3.11

# Set working directory
WORKDIR /app

RUN COMPOSE_BAKE=true
# Install required system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy requirements file first to leverage Docker cache
COPY uv.lock pyproject.toml README.md ./

# Install Python dependencies
RUN uv sync --no-install-package uni_ai_chatbot

# Copy application code
COPY src ./src

RUN uv sync

# Set the default command (this will be overridden by docker-compose)
ENTRYPOINT ["uv", "run", "python", "-m", "uni_ai_chatbot.bot.main"]
