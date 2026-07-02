# Dockerfile for Django Web Application
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file first
COPY requirements.txt .

# Install CPU-only PyTorch first to optimize build size, then install other dependencies
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . .

# Collect static files for production delivery with WhiteNoise
RUN python manage.py collectstatic --noinput

# Expose Django port
EXPOSE 8000

# Start Django Web App using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "core.wsgi:application"]
