import yt_dlp
import json
import unicodedata
import requests
import sqlite3
import traceback
from urllib.parse import urlparse, parse_qs,urljoin
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
AUDIO_DIR = PROJECT_DIR / "audio"
ALBUMS_DIR = PROJECT_DIR / "albums"
ALBUMS_DIR2 = PROJECT_DIR / "albums360"
VIDEOS_DIR = PROJECT_DIR / "videos"
LYRICS_DIR = PROJECT_DIR / "lyrics"
DATABASE_PATH = PROJECT_DIR / "data.db"

def save_thumbnail(video_id, albumname):
    ALBUMS_DIR.mkdir(parents=True, exist_ok=True)
    ALBUMS_DIR2.mkdir(parents=True, exist_ok=True)
    url = f"https://i.ytimg.com/vi_webp/{video_id}/hq720.webp"
    path = ALBUMS_DIR / f"{albumname}.webp"
    url2 = f"https://i.ytimg.com/vi_webp/{video_id}/sd2.webp"
    path2 = ALBUMS_DIR2 / f"{albumname}.webp"
    
    saved_paths = []
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        if response.headers.get("Content-Type", "").startswith("image/"):
            with open(path, "wb") as f:
                f.write(response.content)
            saved_paths.append(str(path))
    except requests.RequestException as e:
        print(f"HQ Thumbnail error: {e}")
        
    try:
        response = requests.get(url2, timeout=15)
        response.raise_for_status()
        if response.headers.get("Content-Type", "").startswith("image/"):
            with open(path2, "wb") as f:
                f.write(response.content)
            saved_paths.append(str(path2))
    except requests.RequestException as e:
        print(f"SD Thumbnail error: {e}")    

    # Returns the list of successfully saved paths, or None if both failed
    return saved_paths if saved_paths else None

lrc_api="https://lrclib.net/api/search"
def download_video(url, file_name):
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    options1 = {
        "retries": 5,
        "fragment_retries": 5,
        "sleep_interval": 2,
        "max_sleep_interval": 5,
        "extractor_retries": 3,
        "format": "bestvideo[height<=1920][ext=webm]+bestaudio[ext=webm]/best[height<=480][ext=webm]",
        "outtmpl": str(VIDEOS_DIR / f"{file_name}.webm"),
        "merge_output_format": "webm",
        "quiet": True,
        "ratelimit": 2000 * 1024,
        "no_warnings": True,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(options1) as ydl:
        ydl.download([url])


def search_video(query, file_name):
    options = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        data = ydl.extract_info(
            f"ytsearch5:{query}",
            download=False
        )

        entries = data.get("entries") or []

        if not entries:
            print("No search results found")
            return 1

        entry = entries[0]

        video_id = entry.get("id")
        if not video_id:
            print("Video ID not found")
            return 1

        url = f"https://www.youtube.com/watch?v={video_id}"

        download_video(url, file_name)
        return 0
def init_db():
    conn=sqlite3.connect(DATABASE_PATH)
    cursor=sqlite3.Cursor(conn)

    cursor.execute("""  
        CREATE TABLE IF NOT EXISTS music (  
            id INTEGER PRIMARY KEY AUTOINCREMENT,  
            audio_id TEXT NOT NULL,  
            title TEXT NOT NULL,  
            duration INT NOT NULL,  
            album TEXT NOT NULL,
            views INTEGER DEFAULT 0,  
            artists TEXT NOT NULL, 
            is_liked BOOLEAN DEFAULT 0
        )  
    """) 
    cursor.execute("""  
        CREATE TABLE IF NOT EXISTS artists (  
            id INTEGER PRIMARY KEY AUTOINCREMENT,  
            artist TEXT,  
            audio_id TEXT NOT NULL  
        )  
    """) 

    cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                last_seen INTEGER NOT NULL,
                visits INTEGER NOT NULL DEFAULT 1,
                is_guest INTEGER NOT NULL DEFAULT 1,
                session_id TEXT
            )
        """)

    user_columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
    if "is_guest" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN is_guest INTEGER NOT NULL DEFAULT 1")
    if "session_id" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN session_id TEXT")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_views (
            user_name TEXT NOT NULL,
            audio_id TEXT NOT NULL,
            last_viewed INTEGER NOT NULL,
            frequency INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY (user_name, audio_id),
            FOREIGN KEY (audio_id)
                REFERENCES music(audio_id)
                ON DELETE CASCADE
        )
    """)
    cursor.execute("PRAGMA foreign_keys = ON")
    conn.commit()  
    conn.close() 



init_db()
options = {
    "outtmpl": {
        "default": str(AUDIO_DIR / "%(id)s.%(ext)s"),
        "thumbnail": str(ALBUMS_DIR / "%(album)s.%(ext)s"),
    },
    "overwrites": False,
    "format": "ba[acodec=opus]/ba",
    "sleep_interval": 2,
    "retries": 5,
    "fragment_retries": 5,
    "extractor_retries": 3,
    "max_sleep_interval": 5,
    "ratelimit": 500 * 1024,
    "windowsfilenames": False,
    "restrictfilenames": False,
    "writethumbnail": True,
    "ignoreerrors": True,
}
def get_dev(a,b):
    if a is None or b is None:
        return 999
    if(a>=b):
        return a-b
    else:
        return b-a

def write_save_lrc(I,p,duration):
    response = requests.get(lrc_api, params=p)
    if response.status_code == 429 or response.status_code == 503:
        return 1
    if response.status_code == 503:
        return 1
    if response.status_code != 200:
        return 1
    try:
        js = response.json()
    except requests.exceptions.JSONDecodeError:
        return 1
    dev = 14324
    lrc = ""
    if not isinstance(js, list):
        return 1

    for o in js:
        if not isinstance(o, dict):
            continue
        dur2 = o.get("duration")
        if dur2 is None:
            dur2 = 0

        d = abs(duration - dur2)
        synced = o.get("syncedLyrics")
        if synced and d < dev:
            dev = d
            lrc = synced


    LYRICS_DIR.mkdir(parents=True, exist_ok=True)
    with open(LYRICS_DIR / f"{I}.lrc", "w", encoding="utf-8") as f:
        f.write(lrc)
        return 0


def after_download(info,is_search_video=True):
    conn=sqlite3.connect(DATABASE_PATH)
    cursor=sqlite3.Cursor(conn)
    p = {  
        "track_name": info.get("title"),  
        "artist_name": info.get("artists")[0]  
    }  
    title=info.get("title")
    album=info.get("album")
    duration=info.get("duration")
    I=info.get("id")
    
    save_thumbnail(I,album)
    cursor.execute("""  
        INSERT INTO music (audio_id, title,duration, album, artists)   
         VALUES (?, ?, ?, ?,?)  
    """, (I, title,duration, album, info["artist"]))  
    
    for artist in info["artists"]:  
        cursor.execute("""  
            INSERT INTO artists(artist,audio_id)  
            VALUES (?,?)  
        """,(artist,I))  

    cursor.execute("""  
        DELETE FROM music  
        WHERE id NOT IN (  
            SELECT MIN(id)  
            FROM music  
            GROUP BY audio_id  
        )  
    """)  

    cursor.execute("""  
        DELETE FROM artists  
        WHERE id NOT IN (  
            SELECT MIN(id)  
            FROM artists  
            GROUP BY artist, audio_id  
        )  
    """)  
    conn.commit()  
    conn.close()  
    for i in range(10):
        try:
            if write_save_lrc(I, p, duration)==0:
                break
        except Exception as e:
            print("Lyrics error:", e)
    print("23444&&_54&6+&;-&")
    if is_search_video:
        search_video(title+" video",I)


def download_song(url,is_search_video=True):
    def hook(d):
        if d["status"] == "finished":
            after_download(d["info_dict"],is_search_video)
    options["progress_hooks"] = [hook]
    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])

def get_video_urls(url: str) -> list[str]:
    options = {
        "extract_flat": True,
        "skip_download":True,
        "ignoreerrors": True,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)

        if not info:
            return []
        with open(PROJECT_DIR / "data.json", "w", encoding="utf-8") as f:
            json.dump(info, f, indent=4, ensure_ascii=False)
        return [info["webpage_url"]]
def add_path(url, path):
    return urljoin(url.rstrip("/") + "/", path.lstrip("/"))

def download_file(url):
    download_song(url)   


def restore_missing_audio():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT audio_id FROM music")
    audio_ids = cursor.fetchall()
    conn.close()

    total = len(audio_ids)
    downloaded = 0
    skipped = 0
    failed = 0

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    for index, (audio_id,) in enumerate(audio_ids, 1):
        audio_path = AUDIO_DIR / f"{audio_id}.webm"

        print(f"\n[{index}/{total}] Checking: {audio_id}")

        if audio_path.exists() and audio_path.stat().st_size > 0:
            print("Already exists. Skipping.")
            skipped += 1
            continue

        url = f"https://youtube.com/watch?v={audio_id}"

        try:
            download_song(url,False)

            if audio_path.exists() and audio_path.stat().st_size > 0:
                downloaded += 1
            else:
                failed += 1

        except Exception as e:
            failed += 1
            print("Error:", e)
            traceback.print_exc()

    print("\n========== SUMMARY ==========")
    print("Total:", total)
    print("Downloaded:", downloaded)
    print("Skipped:", skipped)
    print("Failed:", failed)


import threading

_restore_thread = None

def start_audio_restore():
    global _restore_thread

    if _restore_thread and _restore_thread.is_alive():
        print("Audio restoration already running.")
        return

    _restore_thread = threading.Thread(
        target=restore_missing_audio,
        daemon=True,
        name="audio-restore"
    )

    _restore_thread.start()
