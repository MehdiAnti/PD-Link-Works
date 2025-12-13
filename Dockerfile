FROM python:3.12-slim


RUN apt-get update && apt-get install -y \
    libgtk-4-1 \
    libgraphene-1.0-0 \
    libgstreamer-gl1.0-0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    libenchant-2 \
    libsecret-1-0 \
    libgles2-mesa \
    fonts-liberation \
    wget \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app


COPY requirements.txt .
RUN pip install -r requirements.txt


RUN playwright install


COPY . .

EXPOSE 5000

CMD ["python", "main.py"]

