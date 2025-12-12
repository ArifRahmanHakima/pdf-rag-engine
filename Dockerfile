# Simple Python application image for RAG Anything
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (minimal)
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt --default-timeout=1000

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/rag_storage /app/output logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TQDM_DISABLE=1

# Expose port
EXPOSE 8000

# Default command
CMD ["/bin/bash"]

