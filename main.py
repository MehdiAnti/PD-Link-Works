import os
import re
import json
import requests
from flask import Flask, request, jsonify

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
    headers = {"User-Agent": "TelegramBot"}
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    return r.text

def extract_files_from_viewer_data(html_text):
    pattern = r"window\.viewer_data\s*=\s*({.*?});\s*window\.user_authenticated"
    match = re.search(pattern, html_text, re.DOTALL)
    if not match:
        return []

    json_text = match.group(1)
    try:
        data = json.loads(json_text)
        files = data.get("api_response", {}).get("files", [])
        results = []

        # Skip the first file (gallery itself)
        for f in files[1:]:
            file_id = f.get("id")
            if not file_id:
                continue
            results.append({
                "file_id": file_id,
                "file_url": f"https://pixeldrain.com/api/file/{file_id}",
                "thumbnail_url": f"https://pixeldrain.com/api/file/{file_id}/thumbnail"
            })
        return results
    except json.JSONDecodeError:
        return []

def process_pixeldrain_link(link):
    match = re.search(r"https://pixeldrain\.com/(l|u)/([A-Za-z0-9]+)", link)
    if not match:
        return []

    link_type, link_id = match.groups()

    if link_type == "u":
        # Direct single file
        return [{
            "file_id": link_id,
            "file_url": f"https://pixeldrain.com/api/file/{link_id}",
            "thumbnail_url": f"https://pixeldrain.com/api/file/{link_id}/thumbnail"
        }]
    elif link_type == "l":
        html_text = fetch_html(link)
        return extract_files_from_viewer_data(html_text)

@app.route("/webhook/<token>", methods=["POST"])
def webhook(token):
    if token != TELEGRAM_TOKEN:
        return "forbidden", 403

    update = request.get_json(force=True)
    msg = update.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "")
    username = msg.get("from", {}).get("first_name", "there")

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
            "I’ll reply with direct download links and thumbnails."
        )
        send_message(chat_id, help_text)
    else:
        # Extract all valid Pixeldrain links
        links = re.findall(r"https://pixeldrain\.com/(l|u)/[A-Za-z0-9]+", text)
    
        if not links:
            send_message(chat_id, "Send me a valid Pixeldrain link like https://pixeldrain.com/l/ID or /u/ID")
        elif len(links) > 1:
            send_message(chat_id, "⚠️ Please send only **one Pixeldrain link** at a time.")
        else:
            # Only one link, process it
            link = links[0]
            try:
                files = process_pixeldrain_link(link)
                if not files:
                    send_message(chat_id, "⚠️ No files found in this link.")
                else:
                    response_lines = []
                    for i, f in enumerate(files, 1):
                        line = (
                            f"{i}. ID: {f['file_id']}\n"
                            f"   File: {f['file_url']}\n"
                            f"   Thumbnail: {f['thumbnail_url']}"
                        )
                        response_lines.append(line)
    
                    # Split message if too long
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
                send_message(chat_id, f"⚠️ Error processing link: {e}")

        else:
            send_message(chat_id, "Send me a valid Pixeldrain link like https://pixeldrain.com/l/ID or /u/ID")

    return jsonify(ok=True)

def send_welcome(chat_id, username, user_id):
    text = (
        f'Hello <a href="tg://user?id={user_id}">{username}</a>!\n\n'
        "Send your Pixeldrain URL to get the direct link(s) and thumbnail(s).\n"
        "Example: https://pixeldrain.com/l/ID or /u/ID"
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
