
import yt_dlp
import requests
import json
import argparse
import re
import unicodedata
from pathlib import Path

# ======================================
# CONFIGURATION
# ======================================

SERVER_URL = "https://suneelkumar.pythonanywhere.com"
UPLOAD_URL = SERVER_URL + "/api/upload"

UPLOAD_TOKEN = "6e5f95291d2fc3a11243b14c7b431ed2a71ace2f3271ad640a0fe0034218fc0f"

BASE_DIR = Path(__file__).resolve().parent / "music_upload"

AUDIO_DIR = BASE_DIR / "audio"
ALBUMS_DIR = BASE_DIR / "albums"
ALBUMS_DIR2 = BASE_DIR / "albums360"
LYRICS_DIR = BASE_DIR / "lyrics"

LRC_API = "https://lrclib.net/api/search"


def setup():
    for directory in (
        AUDIO_DIR, ALBUMS_DIR,
        ALBUMS_DIR2, LYRICS_DIR
    ):
        directory.mkdir(parents=True, exist_ok=True)


def safe_name(name):
    name = unicodedata.normalize("NFKC", str(name or "Unknown"))
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    return name.strip(" .")[:180] or "Unknown"


# ======================================
# DOWNLOAD AUDIO
# ======================================


def download_audio(url):

    options = {
        "format": "ba[acodec=opus]/ba",
        "outtmpl": str(AUDIO_DIR / "%(id)s.%(ext)s"),
        "quiet": False,
        "no_warnings": True,
        "noplaylist": True,
        "overwrites": False,
        "retries": 5,
        "fragment_retries": 5,
        "extractor_retries": 3,
        "sleep_interval": 2,
        "max_sleep_interval": 2,
        "ratelimit": 2000 * 1024,
    }

    with yt_dlp.YoutubeDL(options) as ydl:

        info = ydl.extract_info(url, download=True)

        if not info:
            raise Exception("Unable to extract video")

        if info.get("_type") in ("playlist", "multi_video"):
            raise Exception("Expected a single video, got playlist")

        video_id = info["id"]

        candidates = [
            Path(ydl.prepare_filename(info))
        ]

        for item in info.get("requested_downloads") or []:
            if item.get("filepath"):
                candidates.append(Path(item["filepath"]))

        audio_path = next(
            (
                p for p in candidates
                if p.is_file() and p.stat().st_size > 0
            ),
            None
        )

        if audio_path is None:
            audio_path = AUDIO_DIR / f"{video_id}.webm"

        if not audio_path.exists():
            raise Exception(f"Audio file missing: {video_id}")

        return info, audio_path

# ======================================
# DOWNLOAD THUMBNAILS
# ======================================

def download_thumbnail(video_id, album):

    album = safe_name(album)

    urls = [
        (
            f"https://i.ytimg.com/vi_webp/{video_id}/hq720.webp",
            ALBUMS_DIR / f"{album}.webp"
        ),
        (
            f"https://i.ytimg.com/vi_webp/{video_id}/sd2.webp",
            ALBUMS_DIR2 / f"{album}.webp"
        )
    ]

    paths = []

    for url, path in urls:
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()

            if response.headers.get("Content-Type", "").startswith("image/"):
                path.write_bytes(response.content)
                paths.append(path)
            else:
                paths.append(None)

        except requests.RequestException as e:
            print("Thumbnail error:", e)
            paths.append(None)

    return paths


# ======================================
# FETCH LYRICS
# ======================================

def download_lyrics(video_id, title, artists, duration):

    params = {
        "track_name": title,
        "artist_name": artists[0] if artists else ""
    }

    try:
        response = requests.get(
            LRC_API,
            params=params,
            timeout=20
        )
        
        response.raise_for_status()
        results = response.json()
        best_lyrics = ""
        best_difference = float("inf")

        if isinstance(results, list):
            for item in results:

                lyrics = item.get("syncedLyrics")
                song_duration = item.get("duration")

                if not lyrics or song_duration is None:
                    continue

                difference = abs(duration - song_duration)

                if difference < best_difference:
                    best_difference = difference
                    best_lyrics = lyrics

        path = LYRICS_DIR / f"{video_id}.lrc"

        path.write_text(best_lyrics, encoding="utf-8")

        return path

    except Exception as e:
        print("Lyrics error:", e)
        return None


# ======================================
# UPLOAD TO PYTHONANYWHERE
# ======================================

def upload_song(info, audio_path):

    video_id = info["id"]

    title = info.get("title") or "Unknown"
    album = safe_name(info.get("album"))

    artists = info.get("artists") or [
        info.get("artist")
        or info.get("channel")
        or info.get("uploader")
        or "Unknown"
    ]

    duration = int(info.get("duration") or 0)

    metadata = {
        "id": video_id,
        "title": title,
        "album": album,
        "artists": artists,
        "duration": duration
    }

    thumbnails = download_thumbnail(video_id, album)

    lyrics_path = download_lyrics(
        video_id, title, artists, duration
    )

    files = {}

    handles = []

    try:
        audio_file = open(audio_path, "rb")
        handles.append(audio_file)

        files["audio"] = (
            audio_path.name,
            audio_file,
            "audio/webm"
        )

        if thumbnails[0]:
            f = open(thumbnails[0], "rb")
            handles.append(f)
            files["thumbnail"] = (
                thumbnails[0].name, f, "image/webp"
            )

        if thumbnails[1]:
            f = open(thumbnails[1], "rb")
            handles.append(f)
            files["thumbnail360"] = (
                thumbnails[1].name, f, "image/webp"
            )

        if lyrics_path:
            f = open(lyrics_path, "rb")
            handles.append(f)
            files["lyrics"] = (
                lyrics_path.name, f, "text/plain"
            )

        response = requests.post(
            UPLOAD_URL,
            headers={
                "X-Upload-Token": UPLOAD_TOKEN
            },
            data={
                "metadata": json.dumps(
                    metadata, ensure_ascii=False
                )
            },
            files=files,
            timeout=(20, 300)
        )

        print("Server response:", response.status_code)
        print(response.text)

        response.raise_for_status()

        return True

    finally:
        for f in handles:
            f.close()


# ======================================
# MAIN PIPELINE
# ======================================

def process_song(url):

    print("\nDownloading:", url)

    info, audio_path = download_audio(url)

    print("Audio downloaded:", audio_path)

    print("Uploading:", info.get("title"))

    if upload_song(info, audio_path):
        print("SUCCESS:", info["id"])
    else:
        print("UPLOAD FAILED:", info["id"])



def main():

    setup()

    parser = argparse.ArgumentParser(
        description="Download and upload music"
    )

    parser.add_argument(
        "urls",
        nargs="+"
    )

    args = parser.parse_args()

    for url in args.urls:

        try:
            print("\nProcessing:", url)

            # Extract playlist entries without downloading
            extract_options = {
                "extract_flat": True,
                "skip_download": True,
                "quiet": True,
                "ignoreerrors": True,
                "noplaylist": False,
            }

            with yt_dlp.YoutubeDL(extract_options) as ydl:
                result = ydl.extract_info(
                    url,
                    download=False
                )

            if not result:
                print("Unable to extract URL")
                continue

            if result.get("_type") in ("playlist", "multi_video"):
                entries = result.get("entries") or []
            else:
                entries = [result]

            total = len(entries)

            for index, entry in enumerate(entries, 1):

                if not entry:
                    continue

                video_url = (
                    entry.get("url")
                    or entry.get("webpage_url")
                )

                if not video_url:
                    video_id = entry.get("id")
                    if video_id:
                        video_url = (
                            "https://www.youtube.com/watch?v="
                            + video_id
                        )

                if not video_url:
                    print("Skipping entry without URL")
                    continue

                print(f"\n[{index}/{total}] {video_url}")

                try:
                    info, audio_path = download_audio(video_url)

                    print("Downloaded:", info.get("title"))

                    upload_song(info, audio_path)

                    print("SUCCESS:", info["id"])

                except Exception as e:
                    print("SONG FAILED:", e)
                    continue

        except Exception as e:
            print("PLAYLIST FAILED:", e)




if __name__ == "__main__":
    main()
