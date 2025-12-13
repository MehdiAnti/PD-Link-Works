import os
import re
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
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        return r.text
    except requests.RequestException:
        return None

def extract_pixeldrain_ids_from_html(html_text):
    ids = re.findall(r"/file/([A-Za-z0-9]{8})/info", html_text)

    seen = set()
    return [i for i in ids if not (i in seen or seen.add(i))]

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

    if link_type == "l":
        html_text = fetch_html(link)
        if not html_text:
            return []

        ids = extract_pixeldrain_ids_from_html(html_text)
        if not ids:
            return []

        return [{
            "file_id": fid,
            "file_url": f"https://pixeldrain.com/api/file/{fid}",
            "thumbnail_url": f"https://pixeldrain.com/api/file/{fid}/thumbnail"
        } for fid in ids]

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

    return {
        "title": title,
        "file_url": video_url,
        "thumbnail_url": thumbnail_url
    }

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
        send_message(chat_id,
            "Send a Pixeldrain link:\n"
            "https://pixeldrain.com/l/ID (gallery)\n"
            "https://pixeldrain.com/u/ID (single)\n\n"
            "Or a RedGIFs link."
        )

    else:
        pixeldrain_links = is_pixeldrain_link(text)
        redgifs_links = is_redgifs_link(text)

        if pixeldrain_links:
            link = pixeldrain_links[0]
            files = process_pixeldrain_link(link)

            if not files:
                send_message(chat_id, "⚠️ No files found or link inaccessible.")
            else:
                response = ""
                for i, f in enumerate(files, 1):
                    response += (
                        f"{i}. ID: {f['file_id']}\n"
                        f"File: {f['file_url']}\n"
                        f"Thumbnail: {f['thumbnail_url']}\n\n"
                    )

                for chunk in [response[i:i+3500] for i in range(0, len(response), 3500)]:
                    send_message(chat_id, chunk)

        elif redgifs_links:
            data = process_redgifs_link(redgifs_links[0])
            if not data["file_url"]:
                send_message(chat_id, "⚠️ RedGIF link inaccessible.")
            else:
                send_message(chat_id,
                    f"Title: {data['title']}\n\n"
                    f"File:\n{data['file_url']}\n\n"
                    f"Thumbnail:\n{data['thumbnail_url']}"
                )

        else:
            send_message(chat_id, "Send a valid Pixeldrain or RedGIFs link.")

    return jsonify(ok=True)

def send_welcome(chat_id, username, user_id):
    text = (
        f'Hello <a href="tg://user?id={user_id}">{username}</a>!\n\n'
        "Send Pixeldrain or RedGIFs links to get direct files."
    )
    requests.post(f"{BOT_API}/sendMessage", json={
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
