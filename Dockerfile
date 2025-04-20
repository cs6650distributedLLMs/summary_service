FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Set environment variables
ENV PORT=5000
ENV REDIS_HOST=redis
ENV REDIS_PORT=6379
ENV REDIS_PASSWORD=
ENV GROKX_API_KEY=
ENV GROKX_API_URL=https://api.grokx.ai/v1/chat/completions

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]