FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create menus directory if it doesn't exist
RUN mkdir -p menus

# Create non-root user for security
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

# Expose port
EXPOSE $PORT

# Start the application with increased payload size limit
CMD uvicorn main:app --host 0.0.0.0 --port $PORT --limit-concurrency 1000 --limit-max-requests 10000 --timeout-keep-alive 120 