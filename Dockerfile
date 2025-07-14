FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the source code
COPY src/ src/
COPY main.py .

# Create directories for data persistence
RUN mkdir -p /app/checkpoints /app/logs && \
    chown -R appuser:appuser /app

# Make main.py executable
RUN chmod +x main.py

# Switch to non-root user
USER appuser

# Create volumes for persistence
VOLUME ["/app/checkpoints", "/app/logs"]

# Run the application
ENTRYPOINT ["python", "main.py"]
