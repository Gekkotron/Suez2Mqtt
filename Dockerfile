FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Create data directory for cookies
RUN mkdir -p /app/data

# Set Python path to include src directory
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Run as non-root user
RUN useradd -m -u 1000 suez && \
    chown -R suez:suez /app
USER suez

# Default command
CMD ["python", "-m", "suez_mqtt"]
