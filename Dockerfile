# Use official Playwright Python image with browsers pre-installed
FROM mcr.microsoft.com/playwright/python:latest

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

# Copy bot code
COPY . .

EXPOSE 5000

CMD ["python", "main.py"]
