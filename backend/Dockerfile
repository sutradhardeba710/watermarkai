# Use 64-bit Python 3.11 slim as recommended by documentation
FROM python:3.11-slim

# Install system dependencies (ffmpeg, opencv requirements)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY pyproject.toml .
# Install dependencies from pyproject.toml including project itself
RUN pip install --no-cache-dir .

# Copy application code
COPY . .

# Set default command (can be overridden by docker-compose)
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
