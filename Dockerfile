FROM python:3.10-slim

# Install system dependencies and Google Chrome
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    unzip \
    libxi6 \
    libgconf-2-4 \
    libnss3 \
    libfontconfig1 \
    libxrender1 \
    libxext6 \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD gunicorn bot:app --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 120
