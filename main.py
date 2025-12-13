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
    requests.post(
        f"{BOT_API}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )

def fetch_html(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        r = requests.get(url, headers=headers, timeout=8)
        r.raise_for_status()
        return r.text
    except:
        return None

def extract_pixeldrain_ids_from_html(html):
    ids = re.findall(r"/file/([A-Za-z0-9]{8})/info", html)
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

    html = fetch_html(link)
    if not html:
        return []

    ids = extract_pixeldrain_ids_from_html(html)
    if not ids:
        return []

    return [{
        "file_id": fid,
        "file_url": f"https://pixeldrain.com/api/file/{fid}",
        "thumbnail_url": f"https://pixeldrain.com/api/file/{fid}/thumbnail"
    } for fid in ids]

def process_redgifs_link(link):
    html = fetch_html(link)
    if not html:
        return {"title": "", "file_url": "", "thumbnail_url": ""}

    title_match = re.search(r'"headline":"(.*?)"', html)
    file_match = re.search(r'"contentUrl":"(.*?)"', html)
    thumb_match = re.search(r'"thumbnailUrl":"(.*?)"', html)

    return {
        "title": title_match.group(1) if title_match else "No Title",
        "file_url": file_match.group(1).replace("-silent", "") if file_match else "",
        "thumbnail_url": thumb_match.group(1) if thumb_match else ""
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

    pixeldrain_links = is_pixeldrain_link(text)
    redgifs_links = is_redgifs_link(text)

    if pixeldrain_links:
        files = process_pixeldrain_link(pixeldrain_links[0])
        if not files:
            send_message(chat_id, "⚠️ No files found or link inaccessible.")
        else:
            out = ""
            for i, f in enumerate(files, 1):
                out += (
                    f"{i}. ID: {f['file_id']}\n"
                    f"{f['file_url']}\n"
                    f"{f['thumbnail_url']}\n\n"
                )
            for c in [out[i:i+3500] for i in range(0, len(out), 3500)]:
                send_message(chat_id, c)

    elif redgifs_links:
        d = process_redgifs_link(redgifs_links[0])
        if not d["file_url"]:
            send_message(chat_id, "⚠️ RedGIF link inaccessible.")
        else:
            send_message(
                chat_id,
                f"Title: {d['title']}\n\n"
                f"File:\n{d['file_url']}\n\n"
                f"Thumbnail:\n{d['thumbnail_url']}"
            )

    else:
        send_message(chat_id, "Send a valid Pixeldrain or RedGIFs link.")

    return jsonify(ok=True)

def send_welcome(chat_id, username, user_id):
    text = (
        f'Hello <a href="tg://user?id={user_id}">{username}</a>!\n\n'
        "Send Pixeldrain or RedGIFs links to get direct files."
    )
    requests.post(
        f"{BOT_API}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    )

@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    host = request.host_url.rstrip("/")
    webhook_url = f"{host}/webhook/{TELEGRAM_TOKEN}"
    resp = requests.post(f"{BOT_API}/setWebhook", data={"url": webhook_url})
    return (resp.text, resp.status_code)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
