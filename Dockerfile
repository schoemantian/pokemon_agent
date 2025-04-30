FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt space-requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r space-requirements.txt

# Copy project
COPY . .

# Environment variables
ENV BATTLE_FORMAT=gen9randombattle
ENV LLM_PROVIDER=anthropic

# Expose the port that Gradio will run on
EXPOSE 7860

# Set command to run the app
CMD ["python", "deploy.py"]