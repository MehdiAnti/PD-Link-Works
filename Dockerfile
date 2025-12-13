# Use official Playwright Python image with browsers pre-installed
FROM mcr.microsoft.com/playwright/python:latest

# Set working directory
WORKDIR /app

# Copy Python dependencies and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY . .

# Expose Flask port
EXPOSE 5000

# Run the bot
CMD ["python", "main.py"]
