FROM python:3.12-slim

# Install system dependencies for Playwright/Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    unzip \
    ca-certificates \
    fonts-liberation \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libxss1 \
    libasound2 \
    libnss3 \
    libgbm1 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxtst6 \
    libglib2.0-0 \
    libpango-1.0-0 \
    libharfbuzz0b \
    libfreetype6 \
    libfontconfig1 \
    libxrender1 \
    libjpeg62-turbo \
    libxinerama1 \
    libxkbcommon0 \
    libdrm2 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Install Playwright browsers
RUN playwright install

# Copy bot code
COPY . .

# Expose port for Flask
EXPOSE 5000

# Start the bot
CMD ["python", "main.py"]
