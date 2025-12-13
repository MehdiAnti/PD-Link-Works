import os
import re
import json
import requests
import logging
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise RuntimeError("TELEGRAM_TOKEN environment variable is missing")

BOT_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

app = Flask(__name__)

@app.route("/mame", methods=["GET"])
def mame():
    return "Hell yeah, 85 ;)", 200

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

def send_message(chat_id, text):
    url = f"{BOT_API}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text})

def fetch_html(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.text
    except requests.exceptions.RequestException:
        return None

def process_pixeldrain_link(link):
    match = re.search(r"https://pixeldrain\.com/(l|u)/([A-Za-z0-9]+)", link)
    if not match:
        return []
    link_type, link_id = match.groups()
    
    if link_type == "u":
        return [{
            "file_id": link_id,
            "file_url": f"https://pixeldrain.com/api/file/{link_id}",
            "thumbnail_url": f"https://pixeldrain.com/api/file/{link_id}/thumbnail"
        }]
    elif link_type == "l":
        results = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(link, timeout=15000)
                data = page.evaluate("() => window.viewer_data")
                browser.close()
                files = data.get("api_response", {}).get("files", [])
                for f in files:
                    file_id = f.get("id")
                    if file_id:
                        results.append({
                            "file_id": file_id,
                            "file_url": f"https://pixeldrain.com/api/file/{file_id}",
                            "thumbnail_url": f"https://pixeldrain.com/api/file/{file_id}/thumbnail"
                        })
            return results
        except Exception as e:
            logging.error(f"[Pixeldrain Playwright Error] Link {link} → {e}")
            return []


def process_redgifs_link(link):
    html_text = fetch_html(link)
    if not html_text:
        return {"title": "Error", "file_url": "", "thumbnail_url": ""}
    headline_match = re.search(r'"headline":"(.*?)"', html_text)
    title = headline_match.group(1) if headline_match else "No Title"
    content_match = re.search(r'"contentUrl":"(.*?)"', html_text)
    video_url = content_match.group(1).replace("-silent", "") if content_match else ""
    thumb_match = re.search(r'"thumbnailUrl":"(.*?)"', html_text)
    thumbnail_url = thumb_match.group(1) if thumb_match else ""
    return {"title": title, "file_url": video_url, "thumbnail_url": thumbnail_url}

def is_pixeldrain_link(text):
    return re.findall(r"https://pixeldrain\.com/(?:l|u)/[A-Za-z0-9]+", text)

def is_redgifs_link(text):
    return re.findall(r"https?://(?:www\.|v3\.)?redgifs\.com/watch/[A-Za-z0-9]+", text)

@app.route("/webhook/<token>", methods=["POST"])
def webhook(token):
    if token != TELEGRAM_TOKEN:
        return "forbidden", 403
    update = request.get_json(force=True)
    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")
    if not chat_id:
        return jsonify(ok=False), 400

    if text == "/start":
        user_id = msg.get("from", {}).get("id")
        username = msg.get("from", {}).get("first_name", "there")
        send_welcome(chat_id, username, user_id)
    elif text == "/help":
        help_text = (
            "Send a valid Pixeldrain link in this format:\n"
            "https://pixeldrain.com/l/ID  -> Gallery link\n"
            "https://pixeldrain.com/u/ID  -> Single file link\n"
            "Or send a RedGIFs link like https://www.redgifs.com/watch/ID or v3.redgifs.com/watch/ID\n"
            "I’ll reply with direct download links and thumbnails."
        )
        send_message(chat_id, help_text)
    else:
        pixeldrain_links = is_pixeldrain_link(text)
        redgifs_links = is_redgifs_link(text)

        if pixeldrain_links:
            if len(pixeldrain_links) > 1:
                send_message(chat_id, "⚠️ Please send only one Pixeldrain link at a time.")
            else:
                link = pixeldrain_links[0]
                try:
                    files = process_pixeldrain_link(link)
                    if not files:
                        logging.error(f"[Pixeldrain] User sent: {link} → No files found")
                        send_message(chat_id, "⚠️ No files found or link inaccessible.")
                    else:
                        response_lines = []
                        for i, f in enumerate(files, 1):
                            line = (
                                f"{i}. ID: {f['file_id']}\n"
                                f"   File: {f['file_url']}\n"
                                f"   Thumbnail: {f['thumbnail_url']}"
                            )
                            response_lines.append(line)
                        chunk_size = 3500
                        message = ""
                        for line in response_lines:
                            line_text = line + "\n\n"
                            if len(message) + len(line_text) > chunk_size:
                                send_message(chat_id, message)
                                message = line_text
                            else:
                                message += line_text
                        if message:
                            send_message(chat_id, message)
                except Exception as e:
                    logging.error(f"[Pixeldrain Exception] Link {link} → {e}")
                    send_message(chat_id, "⚠️ An unexpected error occurred while processing the link.")
        elif redgifs_links:
            link = redgifs_links[0]
            data = process_redgifs_link(link)
            if not data['file_url']:
                send_message(chat_id, "⚠️ RedGIF link inaccessible or error occurred.")
            else:
                msg_text = (
                    f"Title: {data['title']}\n\n"
                    f"File:\n{data['file_url']}\n\n"
                    f"Thumbnail:\n{data['thumbnail_url']}"
                )
                send_message(chat_id, msg_text)
        else:
            send_message(chat_id, "Send a valid Pixeldrain or RedGIFs link")
    return jsonify(ok=True)

def send_welcome(chat_id, username, user_id):
    text = (
        f'Hello <a href="tg://user?id={user_id}">{username}</a>!\n\n'
        "Send your Pixeldrain URL to get the direct link(s) and thumbnail(s),\n"
        "or RedGIFs URL to get video and thumbnail.\n"
        "Example: https://pixeldrain.com/l/ID or /u/ID\n"
        "Example: https://www.redgifs.com/watch/ID or v3.redgifs.com/watch/ID"
    )
    url = f"{BOT_API}/sendMessage"
    requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    })

@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    host = request.host_url.rstrip("/")
    webhook_url = f"{host}/webhook/{TELEGRAM_TOKEN}"
    resp = requests.post(f"{BOT_API}/setWebhook", data={"url": webhook_url})
    return (resp.text, resp.status_code)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
