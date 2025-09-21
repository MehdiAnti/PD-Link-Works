# PD-Link-Works

A Telegram bot that extracts direct download links and thumbnails from Pixeldrain URLs. Supports single file links (`/u/ID`) and gallery links (`/l/ID`).

Deployed on [Render.com](https://render.com) and kept alive using [UptimeRobot](https://uptimerobot.com/).

## Features

- `/start` and `/help` commands.
- Processes single Pixeldrain file links and gallery links.
- Returns direct download links and thumbnail URLs.
- Works on Render.com with uptime monitoring.

## Requirements

- Python 3.10+
- Flask
- Requests

## Setup Locally

1. Clone the repository:
```bash
git clone https://github.com/MehdiAnti/PD-Link-Works.git
cd pd-link-works
```
2. Create and activate a virtual environment:
```
python -m venv venv
source venv/bin/activate   # Linux / Mac
venv\Scripts\activate      # Windows
```
3. Install dependencies:
```
pip install -r requirements.txt
```
4. Set environment variables:
```
export TELEGRAM_TOKEN=<your-telegram-bot-token>
export PORT=5000   # optional
```
5. Run locally:
```
python main.py
```
The bot will be available at http://localhost:5000.


## Deployment on Render.com

1. Connect your GitHub repo to Render.com.

2. Create a Web Service on Render:
    - Environment: Python 3
    - Start Command: 
gunicorn main:app

    - Environment Variables:
      TELEGRAM_TOKEN=`your-telegram-bot-token`

3. Deploy the service.

4. Set the webhook:
   Open in browser or curl:
GET https://<your-render-app-url>/set_webhook

5. Optional: Use UptimeRobot to ping the Render URL every 5 minutes
   to prevent the service from sleeping on the free tier.

## Usage

Send a Pixeldrain link in a private chat:
```
https://pixeldrain.com/u/ID
https://pixeldrain.com/l/ID
```

The bot responds with:
  - Direct download links
  - Thumbnail links (without Telegram preview)

Commands:
  - /start – Welcome message
  - /help – Instructions

## Notes

  - Only one Pixeldrain link per message.
  - Works with galleries and single files.

## License

This project is licensed under the MIT License.

# Contributing
Contributions are welcome! Please submit bug reports, feature requests, or pull requests via GitHub.

# Disclaimer

This project is provided as-is.
The author is not responsible for any misuse, data loss, or damages resulting from using this bot or the provided code.
Use it at your **own risk**.
