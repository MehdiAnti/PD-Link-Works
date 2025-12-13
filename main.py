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
    requests.post(f"{BOT_API}/sendMessage", json={"chat_id": chat_id, "text": text})

def fetch_html(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        return r.text
    except:
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

    headers = {"User-Agent": "Mozilla/5.0"}
    api_url = f"https://pixeldrain.com/api/list/{link_id}"

    try:
        r = requests.get(api_url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
    except:
        return []

    results = []
    for f in data.get("files", []):
        file_id = f.get("id")
        if file_id:
            results.append({
                "file_id": file_id,
                "file_url": f"https://pixeldrain.com/api/file/{file_id}",
                "thumbnail_url": f"https://pixeldrain.com/api/file/{file_id}/thumbnail"
            })

    return results

def process_redgifs_link(link):
    html_text = fetch_html(link)
    if not html_text:
        return {"title": "Error", "file_url": "", "thumbnail_url": ""}
    title = re.search(r'"headline":"(.*?)"', html_text)
    video = re.search(r'"contentUrl":"(.*?)"', html_text)
    thumb = re.search(r'"thumbnailUrl":"(.*?)"', html_text)
    return {
        "title": title.group(1) if title else "No Title",
        "file_url": video.group(1).replace("-silent", "") if video else "",
        "thumbnail_url": thumb.group(1) if thumb else ""
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
            "Send a Pixeldrain or RedGIFs link:\n"
            "https://pixeldrain.com/u/ID\n"
            "https://pixeldrain.com/l/ID\n"
            "https://www.redgifs.com/watch/ID"
        )

    else:
        pixeldrain_links = is_pixeldrain_link(text)
        redgifs_links = is_redgifs_link(text)

        if pixeldrain_links:
            if len(pixeldrain_links) > 1:
                send_message(chat_id, "⚠️ One Pixeldrain link at a time.")
            else:
                files = process_pixeldrain_link(pixeldrain_links[0])
                if not files:
                    send_message(chat_id, "⚠️ No files found or link inaccessible.")
                else:
                    msg_out = ""
                    for i, f in enumerate(files, 1):
                        line = f"{i}. ID: {f['file_id']}\nFile: {f['file_url']}\nThumbnail: {f['thumbnail_url']}\n\n"
                        if len(msg_out) + len(line) > 3500:
                            send_message(chat_id, msg_out)
                            msg_out = line
                        else:
                            msg_out += line
                    if msg_out:
                        send_message(chat_id, msg_out)

        elif redgifs_links:
            data = process_redgifs_link(redgifs_links[0])
            if not data["file_url"]:
                send_message(chat_id, "⚠️ RedGIF error.")
            else:
                send_message(chat_id,
                    f"Title: {data['title']}\n\n"
                    f"File:\n{data['file_url']}\n\n"
                    f"Thumbnail:\n{data['thumbnail_url']}"
                )
        else:
            send_message(chat_id, "Send a valid Pixeldrain or RedGIFs link")

    return jsonify(ok=True)

def send_welcome(chat_id, username, user_id):
    requests.post(f"{BOT_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": f'Hello <a href="tg://user?id={user_id}">{username}</a>!',
        "parse_mode": "HTML"
    })

@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    url = request.host_url.rstrip("/") + f"/webhook/{TELEGRAM_TOKEN}"
    r = requests.post(f"{BOT_API}/setWebhook", data={"url": url})
    return r.text, r.status_code

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
