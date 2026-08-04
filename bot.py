import os, re, time, requests, tempfile, telebot
from pathlib import Path

BOT_TOKEN = "8884320310:AAG7aBzFf17UTuCVnKGfjVdzkrc9eaLgMLw"
MAX_DURATION = 600

bot = telebot.TeleBot(BOT_TOKEN)

_client_id = None
_client_id_time = 0

def get_client_id():
    global _client_id, _client_id_time
    if _client_id and time.time() - _client_id_time < 43200:
        return _client_id
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    html = requests.get("https://soundcloud.com", headers=headers, timeout=15).text
    for url in reversed(re.findall(r'src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"', html)[-6:]):
        try:
            m = re.search(r'client_id\s*[=:]\s*["\']([a-zA-Z0-9]{32})["\']',
                          requests.get(url, timeout=10).text)
            if m:
                _client_id = m.group(1)
                _client_id_time = time.time()
                return _client_id
        except:
            continue
    raise Exception("SoundCloud ulanishda xato. Keyinroq urinib ko'ring.")

def search_song(query):
    cid = get_client_id()
    r = requests.get(
        f"https://api-v2.soundcloud.com/search/tracks"
        f"?q={requests.utils.quote(query)}&client_id={cid}&limit=10",
        headers={"User-Agent": "Mozilla/5.0"}, timeout=15
    )
    if not r.ok:
        raise Exception("Qidiruv amalga oshmadi. Qayta yuboring.")
    tracks = [
        t for t in r.json().get("collection", [])
        if t.get("media", {}).get("transcodings")
        and 0 < round(t["duration"] / 1000) <= MAX_DURATION
    ]
    if not tracks:
        raise Exception("Musiqa topilmadi. Boshqa nom bilan urinib ko'ring.")
    return tracks[0]

def get_stream_url(track):
    cid = get_client_id()
    tcs = track["media"]["transcodings"]
    tc = (
        next((t for t in tcs if t["format"]["protocol"] == "progressive"
              and "mpeg" in t["format"]["mime_type"]), None)
        or next((t for t in tcs if t["format"]["protocol"] == "progressive"), None)
        or tcs[0]
    )
    resp = requests.get(f"{tc['url']}?client_id={cid}",
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    url = resp.json().get("url")
    if not url:
        raise Exception("Stream URL bo'sh.")
    return url

def download_audio(stream_url, title):
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", title)[:40]
    path = Path(tempfile.gettempdir()) / f"tgbot_{int(time.time())}_{safe}.mp3"
    r = requests.get(stream_url, headers={"User-Agent": "Mozilla/5.0"},
                     stream=True, timeout=120)
    if not r.ok:
        raise Exception("Audio yuklab bo'lmadi.")
    with open(path, "wb") as f:
        for chunk in r.iter_content(65536):
            f.write(chunk)
    return str(path)

def fmt(sec):
    return f"{sec // 60}:{sec % 60:02d}"

# ── /start ────────────────────────────────────────────────────────────────────
@bot.message_handler(commands=["start"])
def on_start(msg):
    bot.send_message(
        msg.chat.id,
        "🎵 <b>Salom! Men musiqa botman.</b>\n\n"
        "Qo'shiq yoki qo'shiqchi nomini yozing — men yuklab beraman.\n\n"
        "<i>Masalan:</i> <code>Ulug'bek Rahmatullayev</code> yoki "
        "<code>Dildora Niyozova Yomg'ir</code>",
        parse_mode="HTML"
    )

# ── Matn → musiqa ─────────────────────────────────────────────────────────────
@bot.message_handler(content_types=["text"])
def on_text(msg):
    query = msg.text.strip()
    if not query or query.startswith("/"):
        return

    status = bot.send_message(msg.chat.id,
                               f"🔍 <b>{query}</b> qidirilmoqda...",
                               parse_mode="HTML")
    try:
        track  = search_song(query)
        title  = track.get("title", query)
        artist = track.get("user", {}).get("username", "Noma'lum")
        dur    = round(track["duration"] / 1000)

        bot.edit_message_text(f"⬇️ Yuklanmoqda: <b>{title}</b>...",
                              msg.chat.id, status.message_id, parse_mode="HTML")

        stream_url = get_stream_url(track)
        file_path  = download_audio(stream_url, title)

        with open(file_path, "rb") as audio:
            bot.send_audio(
                msg.chat.id, audio,
                title=title,
                performer=artist,
                caption=f"🎵 <b>{title}</b>\n👤 {artist}\n⏱ {fmt(dur)}",
                parse_mode="HTML"
            )

        bot.delete_message(msg.chat.id, status.message_id)
        os.remove(file_path)

    except Exception as e:
        err = str(e)
        text = (f"❌ {err}" if any(w in err for w in ["topilmadi", "uzun", "xato"])
                else f"❌ Uzr, <b>{query}</b> yuklanmadi. Boshqa nom bilan urinib ko'ring.")
        try:
            bot.edit_message_text(text, msg.chat.id, status.message_id, parse_mode="HTML")
        except:
            bot.send_message(msg.chat.id, text, parse_mode="HTML")

# ── Ishga tushirish ───────────────────────────────────────────────────────────
print("✅ Bot ishga tushdi. To'xtatish uchun Ctrl+C")
bot.infinity_polling(timeout=30, long_polling_timeout=20)
  
