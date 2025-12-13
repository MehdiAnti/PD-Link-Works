import os
import re
import json
import logging
import requests
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

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
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        return r.text
    except Exception as e:
        logging.error(f"[FETCH_HTML] {url} → {e}")
        return None

def extract_ids_from_html(html):
    ids = re.findall(r"/file/([A-Za-z0-9]{8})/info", html)
    seen = set()
    return [i for i in ids if not (i in seen or seen.add(i))]

def fetch_ids_from_api(list_id):
    api_url = f"https://pixeldrain.com/api/list/{list_id}"
    try:
        r = requests.get(api_url, timeout=10)
        r.raise_for_status()
        data = r.json()
        files = data.get("files", [])
        return data, [f["id"] for f in files if "id" in f]
    except Exception as e:
        logging.error(f"[PIXELDRAIN API ERROR] {e}")
        return None, []

def process_pixeldrain_link(link, chat_id):
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
    if html:
        ids = extract_ids_from_html(html)
        if ids:
            logging.info(f"[PIXELDRAIN HTML OK] {link_id} → {len(ids)} files")
            return [{
                "file_id": i,
                "file_url": f"https://pixeldrain.com/api/file/{i}",
                "thumbnail_url": f"https://pixeldrain.com/api/file/{i}/thumbnail"
            } for i in ids]

    logging.warning(f"[PIXELDRAIN HTML FAILED] {link_id} → trying API")

    api_data, ids = fetch_ids_from_api(link_id)
    if api_data:
        short_api = json.dumps(api_data, indent=2)[:3500]
        send_message(chat_id, f"[API fallback used]\n\n{short_api}")

    if ids:
        logging.info(f"[PIXELDRAIN API OK] {link_id} → {len(ids)} files")
        return [{
            "file_id": i,
            "file_url": f"https://pixeldrain.com/api/file/{i}",
            "thumbnail_url": f"https://pixeldrain.com/api/file/{i}/thumbnail"
        } for i in ids]

    logging.error(f"[PIXELDRAIN FAILED] {link_id}")
    return []

def process_redgifs_link(link):
    html = fetch_html(link)
    if not html:
        return {"title": "", "file_url": "", "thumbnail_url": ""}

    title = re.search(r'"headline":"(.*?)"', html)
    file_url = re.search(r'"contentUrl":"(.*?)"', html)
    thumb = re.search(r'"thumbnailUrl":"(.*?)"', html)

    return {
        "title": title.group(1) if title else "No Title",
        "file_url": file_url.group(1).replace("-silent", "") if file_url else "",
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

    logging.info(f"[USER] {chat_id} → {text}")

    if not chat_id:
        return jsonify(ok=False), 400

    pixeldrain_links = is_pixeldrain_link(text)
    redgifs_links = is_redgifs_link(text)

    if pixeldrain_links:
        files = process_pixeldrain_link(pixeldrain_links[0], chat_id)
        if not files:
            send_message(chat_id, "⚠️ No files found.")
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
        send_message(chat_id, f"{d['file_url']}\n{d['thumbnail_url']}")

    else:
        send_message(chat_id, "Send a Pixeldrain or RedGIFs link")

    return jsonify(ok=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
