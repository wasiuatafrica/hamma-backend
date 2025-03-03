FROM python:3.12.9

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc redis-server && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install  -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Create startup script
RUN chmod +x start.sh stop.sh

# Start services
CMD ["./start.sh"]