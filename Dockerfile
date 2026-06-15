FROM python:3.11-slim

# Set up user 1000 (Hugging Face default UID)
RUN useradd -m -u 1000 user

WORKDIR /app

# Install system dependencies for PyMuPDF and ONNX
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and set ownership
COPY --chown=user:user . .

# Create directories and set permissions for user 1000
RUN mkdir -p uploads chroma_db && \
    chown -R user:user /app && \
    chmod -R 777 /app

# Switch to non-root user
USER 1000

# Expose Hugging Face default port
EXPOSE 7860

# Start server
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
