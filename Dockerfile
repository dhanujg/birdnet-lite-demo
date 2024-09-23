# Use Python 3.7 slim image for ARM64 architecture (Raspberry Pi)
# Authors: Dhanuj Gandikota

FROM arm64v8/python:3.7-slim-buster

# Install necessary system packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libsndfile1 \
    portaudio19-dev \
    libasound2-dev \
    alsa-utils \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Install numpy separately
RUN pip install --no-cache-dir numpy

# Install tflite-runtime for Python 3.7 on ARM64 from the Coral repository
RUN pip install --extra-index-url https://google-coral.github.io/py-repo/ tflite-runtime==2.9.1

# Copy and install Python dependencies
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy application code
COPY . /app
WORKDIR /app

# Set the entry point to run the main script
CMD ["python", "main.py"]
