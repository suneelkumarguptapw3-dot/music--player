from flask import session,abort, Flask, request, jsonify, send_file, render_template, make_response, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import urllib.parse
from pathlib import Path
import uuid
import time
import json
import re
import unicodedata
#from main import download_file, download_song, write_save_lrc
import sqlite3
import os
from datetime import datetime
from functools import wraps


def format_timestamp(timestamp):
    if timestamp is None:
        return None

    return datetime.fromtimestamp(timestamp).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
PROJECT_DIR = Path(__file__).resolve().parent
AUDIO_DIR = PROJECT_DIR / "audio"
ALBUMS_DIR = PROJECT_DIR / "albums"
ALBUMS_DIR2 = PROJECT_DIR / "albums360"
LYRICS_DIR = PROJECT_DIR / "lyrics"

DATABASE_PATH = PROJECT_DIR / "data.db"
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,
    PERMANENT_SESSION_LIFETIME=604800,
)
def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row

        user = conn.execute("""
            SELECT id, username, is_guest
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()

        return dict(user) if user else None
def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = get_current_user()

        if not user:
            return jsonify({"error": "Please login first"}), 401

        if user["is_guest"] or (user["username"] or "").lower() != "admin":
            return jsonify({"error": "Admin access only"}), 403

        return func(*args, **kwargs)

    return wrapper
def init_db():
    with sqlite3.connect(DATABASE_PATH) as conn:

        conn.execute("PRAGMA foreign_keys = ON")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS music (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audio_id TEXT NOT NULL,
                title TEXT NOT NULL,
                duration INT NOT NULL,
                album TEXT NOT NULL,
                artists TEXT NOT NULL,
                is_liked BOOLEAN DEFAULT 0,
                views INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS artists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artist TEXT,
                audio_id TEXT NOT NULL
            )
        """)

        conn.execute("""
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

        user_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(users)")
        }

        if "is_guest" not in user_columns:
            conn.execute("""
                ALTER TABLE users
                ADD COLUMN is_guest INTEGER NOT NULL DEFAULT 1
            """)

        if "session_id" not in user_columns:
            conn.execute("""
                ALTER TABLE users
                ADD COLUMN session_id TEXT
            """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_views (
                user_name TEXT NOT NULL,
                audio_id TEXT NOT NULL,
                last_viewed INTEGER NOT NULL,
                frequency INTEGER NOT NULL DEFAULT 1,
                is_liked BOOLEAN NOT NULL DEFAULT 0,
                end_point INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_name, audio_id)
            )
        """)

        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_user_views_user_audio
            ON user_views(user_name, audio_id)
        """)

        conn.commit()


init_db()
@app.before_request
def identify_user():
    if request.path == "/manifest.json" or request.path.startswith("/static/"):
        return

    now = int(time.time())
    is_home = request.path == "/"

    with sqlite3.connect(DATABASE_PATH) as conn:
        session_id = session.get("session_id")
        user_id = session.get("user_id")

        if session_id and user_id:
            cursor = conn.execute("""
                UPDATE users
                SET last_seen = ?,
                    visits = visits + ?
                WHERE id = ? AND session_id = ? AND is_guest = 0
            """, (now, int(is_home), user_id, session_id))

            if cursor.rowcount:
                return

            session.pop("user_id", None)
            session.pop("session_id", None)

        guest_id = request.cookies.get("guest_id")

        if guest_id:
            row = conn.execute(
                "SELECT id FROM users WHERE id = ? AND is_guest = 1",
                (guest_id,),
            ).fetchone()

            if row:
                conn.execute("""
                    UPDATE users
                    SET last_seen = ?,
                        visits = visits + ?
                    WHERE id = ?
                """, (now, int(is_home), row[0]))

                session["user_id"] = row[0]
                session["identity_type"] = "guest"
                return

        guest_id = str(uuid.uuid4())

        conn.execute("""
            INSERT INTO users (
                id, username, password_hash, created_at,
                last_seen, visits, is_guest, session_id
            ) VALUES (?, ?, ?, ?, ?, ?, 1, NULL)
        """, (
            guest_id,
            guest_id,
            generate_password_hash(guest_id),
            now,
            now,
            int(is_home),
        ))

    session["user_id"] = guest_id
    session["identity_type"] = "guest"

    response = make_response("")
    response.set_cookie(
        "guest_id",
        guest_id,
        max_age=60 * 60 * 24 * 365,
        httponly=True,
        samesite="Lax"
    )
    request.guest_response = response

@app.after_request
def attach_guest_cookie(response):
    guest_response = getattr(request, "guest_response", None)
    if guest_response:
        for cookie in guest_response.headers.getlist("Set-Cookie"):
            response.headers.add("Set-Cookie", cookie)
    return response

@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if not username or not password:
        return jsonify({"success": False, "error": "Username and password are required"}), 400

    now = int(time.time())
    with sqlite3.connect(DATABASE_PATH) as conn:
        row = conn.execute("""
            SELECT id, password_hash
            FROM users
            WHERE LOWER(username) = LOWER(?) AND is_guest = 0
        """, (username,)).fetchone()

        if not row or not check_password_hash(row[1], password):
            return jsonify({"success": False, "error": "Invalid username or password"}), 401

        user_id = row[0]
        new_session_id = str(uuid.uuid4())
        conn.execute("""
            UPDATE users
            SET session_id = ?, last_seen = ?, visits = visits + 1
            WHERE id = ?
        """, (new_session_id, now, user_id))

    session.clear()
    session["user_id"] = user_id
    session["session_id"] = new_session_id
    session["identity_type"] = "account"
    session.permanent = True
    return jsonify({"success": True, "username": username})
@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if not username or not password:
        return jsonify({"success": False, "error": "Username and password are required"}), 400
    if len(username) > 64:
        return jsonify({"success": False, "error": "Username is too long"}), 400
    if len(password) < 8:
        return jsonify({"success": False, "error": "Password must be at least 8 characters"}), 400

    now = int(time.time())
    with sqlite3.connect(DATABASE_PATH) as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE LOWER(username) = LOWER(?)",
            (username,),
        ).fetchone()
        if existing:
            return jsonify({"success": False, "error": "Username already exists"}), 409

        guest_id = session.get("user_id")
        guest = conn.execute(
            "SELECT id FROM users WHERE id = ? AND is_guest = 1",
            (guest_id,),
        ).fetchone()

        if guest:
            user_id = guest_id
            conn.execute("""
                UPDATE users
                SET username = ?, password_hash = ?, is_guest = 0,
                    last_seen = ?, session_id = NULL
                WHERE id = ?
            """, (username, generate_password_hash(password), now, user_id))
        else:
            user_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO users (
                    id, username, password_hash, created_at, last_seen,
                    visits, is_guest, session_id
                ) VALUES (?, ?, ?, ?, ?, 1, 0, NULL)
            """, (user_id, username, generate_password_hash(password), now, now))

    session.pop("identity_type", None)
    session["user_id"] = user_id

    new_session_id = str(uuid.uuid4())
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            "UPDATE users SET session_id = ? WHERE id = ?",
            (new_session_id, user_id),
        )
    session["session_id"] = new_session_id
    session["identity_type"] = "account"
    session.permanent = True

    return jsonify({"success": True, "username": username})


@app.post("/api/logout")
def logout():
    user_id = session.get("user_id")
    session_id = session.get("session_id")

    if user_id and session_id:
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.execute(
                "UPDATE users SET session_id = NULL WHERE id = ? AND session_id = ?",
                (user_id, session_id),
            )

    session.clear()
    response = jsonify({"success": True})
    response.delete_cookie("guest_id")
    return response


@app.get("/api/me")
def identity_status():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False, "identity_type": "guest"})

    with sqlite3.connect(DATABASE_PATH) as conn:
        row = conn.execute("""
            SELECT id, username, created_at, last_seen, visits, is_guest
            FROM users WHERE id = ?
        """, (user_id,)).fetchone()

    if not row:
        session.clear()
        return jsonify({"authenticated": False, "identity_type": "guest"})

    is_guest = bool(row[5])
    return jsonify({
        "authenticated": not is_guest,
        "identity_type": "guest" if is_guest else "account",
        "user_id": row[0],
        "username": row[1] if not is_guest else None,
        "created_at": row[2],
        "last_seen": row[3],
        "visits": row[4],
        "session_active": bool(session.get("session_id")) if not is_guest else False,
    })




@app.post("/api/updatesongviews")
def updatesongviews():
    data = request.get_json(silent=True) or {}

    audio_id = data.get("audio_id")
    endpoint = data.get("endpoint", 0)
    update_only = data.get("update_only", False)

    if not audio_id:
        return jsonify({
            "success": False,
            "error": "audio_id is required"
        }), 400

    try:
        endpoint = int(endpoint)
        if endpoint < 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "error": "Invalid endpoint"
        }), 400

    user_id = session.get("user_id")

    if not user_id:
        return jsonify({
            "success": False,
            "error": "Authentication required"
        }), 401

    with sqlite3.connect(DATABASE_PATH) as conn:
        user_row = conn.execute("""
            SELECT username FROM users WHERE id = ?
        """, (user_id,)).fetchone()

        user_name = user_row[0] if user_row else user_id
        viewed_last = int(time.time())

        if not update_only:
            conn.execute("""
                UPDATE music
                SET views = views + 1
                WHERE audio_id = ?
            """, (audio_id,))

        conn.execute("""
            INSERT INTO user_views (
                user_name,
                audio_id,
                last_viewed,
                frequency,
                end_point
            )
            VALUES (?, ?, ?, ?, ?)

            ON CONFLICT(user_name, audio_id)
            DO UPDATE SET
                frequency = frequency + excluded.frequency,
                last_viewed = excluded.last_viewed,
                end_point = excluded.end_point

        """, (
            user_name,
            audio_id,
            viewed_last,
            0 if update_only else 1,
            endpoint
        ))

    return jsonify({"success": True})
def get_pagination():
    try:
        start = int(request.args.get("start", 0))
        end_value = request.args.get("end")
        end = int(end_value) if end_value is not None else start + 50
    except ValueError:
        return None, None

    if start < 0 or end <= start:
        return None, None

    return start, end
@app.get("/api/music/<path>")
def get_music(path):
    path=urllib.parse.unquote(path)
    path=PROJECT_DIR / 'audio' / path
    if path.exists():
        return send_file(str(path),as_attachment=False)
    return send_file(str(path).replace("opus","webm"),as_attachment=False)

@app.get("/api/video/<path>")
def get_video(path):
    path=urllib.parse.unquote(path)
    path=PROJECT_DIR / 'videos' / path
    return send_file(path,as_attachment=False)


@app.route("/api/lyric/<path>")
def get_lyric(path):
    path=urllib.parse.unquote(path)
    path=PROJECT_DIR / 'lyrics' / path
    if path.exists() == False:
        return {}
    with open(path,"r",encoding="utf-8") as f:
        text= f.read()
        arr=[""]
        i=0
        for ch in text:
            if ch=="\n":
                arr.append("")
                i+=1
            else:
                arr[i]+=ch
        lyrics={}
        for line in arr:
            if line.strip() == "" or "[ti:" in line or "[ar:" in line or "[al:" in line or "[au" in line or "[length" in line or "[by" in line  or "[by:" in line or "[length:" in line:
                continue
            if line[0]=="[":
                time_str=line[1:line.index("]")]
                minutes, seconds = time_str.split(":")
                time = int(minutes) * 60 + float(seconds)
                lyrics[time]=line[line.index("]")+1:]
        return lyrics

@app.route('/api/thumbnail/<path>')
def get_thmb(path):
    query = request.args.get("maxres", "").strip()
    path=urllib.parse.unquote(path)
    p=PROJECT_DIR / 'albums360' / path
    if query == "1":
        p=PROJECT_DIR / 'albums' / path
    return send_file(p)

@app.route("/player")
def index():
    return send_file(PROJECT_DIR / "player.html")

@app.post("/api/download")
def d():
    j=request.get_json()
    download_file(j["url"])
    return "done"
@app.get("/api/history/tracks/")
def history_tracks():
    user_id = session.get("user_id")
    
    if not user_id:
        return jsonify({"error": "User not identified"}), 401

    files = []
    start, end = get_pagination()
    if start is None:
        return jsonify({"error": "Invalid pagination"}), 400

    limit = end - start
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("""
            SELECT
                m.*,
                uv.last_viewed,
                uv.frequency,
                uv.end_point
            FROM user_views AS uv
            INNER JOIN music AS m
                ON uv.audio_id = m.audio_id
            INNER JOIN users AS u
                ON uv.user_name = u.username
            WHERE u.id = ?
            ORDER BY uv.last_viewed DESC
            LIMIT ? OFFSET ?
        """, (user_id,limit,start))

        for row in cursor.fetchall():
            audio_id = row["audio_id"]
            album = row["album"]

            a = {
                "id": audio_id,
                "title": row["title"],
                "duration": row["duration"],
                "album": album,
                "audio": urllib.parse.quote(
                    f"/api/music/{audio_id}.webm"
                ),
                "thumbnail": f"/api/thumbnail/{album}.webp",
                "artists": row["artists"],
                "is_liked": row["is_liked"],
                "views": row["views"],
                "last_viewed": row["last_viewed"],
                "frequency": row["frequency"],
                "endpoint":row["end_point"]
            }
            video_path = PROJECT_DIR / "videos" / f"{audio_id}.webm"

            if video_path.exists():
                a["video"] = urllib.parse.quote(
                    f"/api/video/{audio_id}.webm"
                )
            else:
                a["video"] = "na"

            files.append(a)
    return jsonify(files)
@app.get("/api/tracks")
@app.get("/api/tracks/")
def e():
    current_user = get_current_user()
    user_name = (
        current_user["username"]
        if current_user and not current_user["is_guest"]
        else None
    )
    start, end = get_pagination()
    if start is None:
        return jsonify({"error": "Invalid pagination"}), 400

    limit = end - start
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                m.*,
                COALESCE(uv.is_liked, 0) AS user_is_liked,
                COALESCE(uv.end_point, 0) AS end_point
            FROM music AS m
            LEFT JOIN user_views AS uv
                ON uv.audio_id = m.audio_id
                AND uv.user_name = ?
            ORDER BY m.views DESC
            LIMIT ? OFFSET ?
        """, (user_name,limit,start))

        rows = cursor.fetchall()

    files = []

    for row in rows:
        audio_id = row["audio_id"]
        album = row["album"]

        a = {
            "id": audio_id,
            "title": row["title"],
            "duration": row["duration"],
            "album": album,
            "audio": urllib.parse.quote(
                f"/api/music/{audio_id}.webm"
            ),
            "thumbnail": f"/api/thumbnail/{album}.webp",
            "artists": row["artists"],
            "is_liked": bool(row["user_is_liked"]),
            "views": row["views"],
            "endpoint":row["end_point"]
        }

        video_path = PROJECT_DIR / "videos" / f"{audio_id}.webm"

        a["video"] = (
            urllib.parse.quote(f"/api/video/{audio_id}.webm")
            if video_path.exists()
            else "na"
        )

        files.append(a)

    return jsonify(files)

@app.get("/search")
def search():
    query = request.args.get("q", "").strip()

    if not query:
        return []

    user = get_current_user()
    username = user["username"] if user else None
    escaped = (
        query.replace("\\", "\\\\")
             .replace("%", "\\%")
             .replace("_", "\\_")
    )
    pattern = f"%{escaped}%"
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                m.id,
                m.audio_id,
                m.title,
                m.duration,
                m.album,
                m.artists,
                m.views,
                m.likes,
                COALESCE(uv.is_liked, 0) AS is_liked,
                COALESCE(uv.end_point, 0) AS end_point
            FROM music AS m
            LEFT JOIN user_views AS uv
                ON uv.audio_id = m.audio_id
                AND uv.user_name = ?
            WHERE
                m.audio_id LIKE ? ESCAPE '\\'
                OR m.title LIKE ? ESCAPE '\\'
                OR m.artists LIKE ? ESCAPE '\\'
                OR m.album LIKE ? ESCAPE '\\'
            ORDER BY m.id DESC
            LIMIT 7
            """,
            (username, pattern, pattern, pattern, pattern),
        )
        rows = cursor.fetchall()
    files = []
    for row in rows:
        audio_id = row["audio_id"]
        video_path = PROJECT_DIR / "videos" / f"{audio_id}.webm"
        files.append({
            "id": audio_id,
            "title": row["title"],
            "duration": row["duration"],
            "album": row["album"],
            "audio": urllib.parse.quote(
                f"/api/music/{audio_id}.webm"
            ),
            "video": (
                urllib.parse.quote(
                    f"/api/video/{audio_id}.webm"
                )
                if video_path.exists()
                else "na"
            ),
            "thumbnail": f"/api/thumbnail/{row['album']}.webp",
            "artists": row["artists"],
            "likes": row["likes"],
            "is_liked": bool(row["is_liked"]),
            "views": row["views"],
            "endpoint":row["end_point"]
        })
    return files

@app.route("/hello")
def indejj():
    return send_file(PROJECT_DIR / "artists.html")

@app.get("/api/artists")
def get_all_artists():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT DISTINCT artist FROM artists")
    artists = [row[0] for row in cursor.fetchall()]

    conn.close()
    return artists
@app.route("/artist")
def hhggcc():
    return render_template("artist_tracks.html")
@app.get("/api/artist")
def get_artist():
    artist_name = urllib.parse.unquote(
        request.args.get("artist_name", "")
    )

    user = get_current_user()
    username = user["username"] if user else None
    start, end = get_pagination()
    if start is None:
        return jsonify({"error": "Invalid pagination"}), 400

    limit = end - start
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                m.*,
                COALESCE(uv.is_liked, 0) AS user_is_liked,
                COALESCE(uv.end_point, 0) AS end_point
            FROM music AS m
            JOIN artists AS a
                ON m.audio_id = a.audio_id
            LEFT JOIN user_views AS uv
                ON uv.audio_id = m.audio_id
                AND uv.user_name = ?
            WHERE a.artist = ?
            ORDER BY m.views DESC LIMIT ? OFFSET ?
        """, (username, artist_name,limit,start))

        files = []

        for row in cursor.fetchall():
            audio_id = row[1]

            a = {
                "id": audio_id,
                "title": row[2],
                "duration": row[3],
                "album": row[4],
                "artists": row[5],
                "audio": urllib.parse.quote(
                    f"/api/music/{audio_id}.webm"
                ),
                "likes": row[8],
                "is_liked": bool(row[9]),
                "endpoint":row[10],
                "thumbnail": f"/api/thumbnail/{row[4]}.webp"
            }

            if (PROJECT_DIR / "videos" / f"{audio_id}.webm").exists():
                a["video"] = urllib.parse.quote(
                    f"/api/video/{audio_id}.webm"
                )
            else:
                a["video"] = "na"

            files.append(a)

    return files
@app.get("/artists")
def hfggggg():
    return render_template("artist.html")
@app.get("/api/album/<id>")
def gge(id):
    id = urllib.parse.unquote(id)
    user = get_current_user()
    username = user["username"] if user else None
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    start, end = get_pagination()
    if start is None:
        return jsonify({"error": "Invalid pagination"}), 400

    limit = end - start
    cursor.execute("""
        SELECT
            m.*,
            COALESCE(uv.is_liked, 0) AS user_is_liked,
            COALESCE(uv.end_point, 0) AS end_point
        FROM music AS m
        LEFT JOIN user_views AS uv
            ON uv.audio_id = m.audio_id
            AND uv.user_name = ?
        WHERE m.album = ?
        ORDER BY m.id ASC
        LIMIT ? OFFSET ?
    """, (username, id,limit,start))

    files = []
    for row in cursor.fetchall():
        a = {}
        a["id"] = row[1]
        a["title"] = row[2]
        a["duration"] = row[3]
        a["album"] = row[4]
        a["audio"] = urllib.parse.quote(
            f"/api/music/{row[1]}.webm"
        )
        if (PROJECT_DIR / "videos" / f"{row[1]}.webm").exists():
            a["video"] = urllib.parse.quote(
                f"/api/video/{row[1]}.webm"
            )
        else:
            a["video"] = "na"
        a["thumbnail"] = urllib.parse.quote(
            f"/api/thumbnail/{row[4]}.webp"
        )

        a["artists"] = row[5]
        a["likes"] = row[8]
        a["is_liked"] = bool(row[9])
        a["endpoint"]=row[10]

        files.append(a)
    conn.close()
    return files

@app.get("/api/tracks/liked")
def get_liked_songs():
    user = get_current_user()

    if not user:
        return jsonify({"error": "User not logged in"}), 401

    username = user["username"]

    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute("""
            SELECT
                m.audio_id,
                m.title,
                m.duration,
                m.album,
                m.artists,
                m.views,
                m.likes,
                uv.is_liked,
                uv.end_point
            FROM music AS m
            JOIN user_views AS uv
                ON uv.audio_id = m.audio_id
            WHERE
                uv.user_name = ?
                AND uv.is_liked = 1
            ORDER BY uv.last_viewed DESC
        """, (username,)).fetchall()

    files = []

    for row in rows:
        audio_id = row["audio_id"]

        video_path = PROJECT_DIR / "videos" / f"{audio_id}.webm"

        files.append({
            "id": audio_id,
            "title": row["title"],
            "duration": row["duration"],
            "album": row["album"],
            "artists": row["artists"],
            "audio": urllib.parse.quote(
                f"/api/music/{audio_id}.webm"
            ),
            "video": (
                urllib.parse.quote(
                    f"/api/video/{audio_id}.webm"
                )
                if video_path.exists()
                else "na"
            ),
            "thumbnail": urllib.parse.quote(
                f"/api/thumbnail/{row['album']}.webp"
            ),
            "likes": row["likes"],
            "views": row["views"],
            "is_liked": bool(row["is_liked"]),
            "endpoint":row["end_point"]
        })

    return jsonify(files)
@app.route("/api/metadata/<id>", methods=["GET", "POST"])
def get_123(id):
    current_user = get_current_user()
    user_name = (
        current_user["username"]
        if current_user and not current_user["is_guest"]
        else None
    )
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if request.method == "POST":
            if not user_name:
                return jsonify({"error": "Login required"}), 401
            data = request.get_json(silent=True) or {}
            if not isinstance(data.get("is_liked"), bool):
                return jsonify({
                    "error": "is_liked must be a boolean"
                }), 400
            is_liked = int(data["is_liked"])
            try:
                cursor.execute("""
                    SELECT 1 FROM music WHERE audio_id = ?
                """, (id,))

                if cursor.fetchone() is None:
                    return jsonify({
                        "error": "Metadata not found"
                    }), 404
                cursor.execute("""
                    INSERT INTO user_views (
                        user_name,
                        audio_id,
                        last_viewed,
                        frequency,
                        is_liked
                    )
                    VALUES (?, ?, ?, 1, ?)

                    ON CONFLICT(user_name, audio_id)
                    DO UPDATE SET
                        is_liked = excluded.is_liked
                """, (
                    user_name,
                    id,
                    int(time.time()),
                    is_liked
                ))
                cursor.execute("""
                    UPDATE music
                    SET likes = (
                        SELECT COUNT(*)
                        FROM user_views
                        WHERE audio_id = ?
                        AND is_liked = 1
                    )
                    WHERE audio_id = ?
                """, (id, id))
                conn.commit()
                cursor.execute("""
                    SELECT likes
                    FROM music
                    WHERE audio_id = ?
                """, (id,))

                total_likes = cursor.fetchone()["likes"]
                return jsonify({
                    "id": id,
                    "is_liked": bool(is_liked),
                    "likes": total_likes
                })
            except sqlite3.Error as e:
                conn.rollback()
                return jsonify({"error": str(e)}), 500
        cursor.execute("""
            SELECT
                m.*,
                COALESCE(uv.is_liked, 0) AS user_is_liked,
                COALESCE(uv.end_point, 0) AS end_point
            FROM music AS m
            LEFT JOIN user_views AS uv
                ON uv.audio_id = m.audio_id
                AND uv.user_name = ?
            WHERE m.audio_id = ?
        """, (user_name, id))
        row = cursor.fetchone()
        if row is None:
            return jsonify({
                "error": "Metadata not found"
            }), 404
        audio_id = row["audio_id"]
        if (PROJECT_DIR / "videos" / f"{audio_id}.webm").exists():
            video = urllib.parse.quote(
                f"/api/video/{audio_id}.webm"
            )
        else:
            video = "na"

        if not get_lyric(id + ".lrc"):
            print("searching lyrics")

            p = {
                "track_name": row["title"],
                "artist_name": row["artists"]
            }
            write_save_lrc(id, p, row["duration"])
        return jsonify({
            "id": audio_id,
            "title": row["title"],
            "duration": row["duration"],
            "album": row["album"],
            "video": video,
            "audio": urllib.parse.quote(
                f"/api/music/{audio_id}.webm"
            ),
            "thumbnail": urllib.parse.quote(
                f"/api/thumbnail/{row['album']}.webp"
            ),
            "artists": row["artists"],
            "lyrics": get_lyric(id + ".lrc") or {},
            "is_liked": bool(row["user_is_liked"]),
            "likes": row["likes"],
            "views":row["views"],
            "endpoint":row[10]
        })

@app.post("/download")
def bbvd():
    j=request.get_json()
    print(j)
    download_file(j["url"])
    return "done"
@app.get("/api/album")
def get_albums():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    start, end = get_pagination()
    if start is None:
        return jsonify({"error": "Invalid pagination"}), 400

    limit = end - start
    try:
        cursor.execute("""
            SELECT DISTINCT album
            FROM music
            WHERE album IS NOT NULL AND album != ''
            ORDER BY album LIMIT ? OFFSET ?
        """,(limit,start))
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()

@app.route("/manifest.json")
def manifest():
    return send_file(PROJECT_DIR / "manifest.json")

ALLOWED_TABLES = {
    "music",
    "artists",
    "users",
    "user_views"
}

DATE_COLUMNS = {
    "created_at",
    "last_seen",
    "last_viewed"
}

@app.route(
    "/api/dashboard",
    methods=["GET", "POST", "PATCH", "PUT", "DELETE"]
)
@admin_required
def dashboard():
    table = request.args.get("table")
    row_id = request.args.get("id")
    if table is not None and table not in ALLOWED_TABLES:
        return jsonify({"error": "Invalid table"}), 400
    conn = None
    def quote(name):
        return '"' + name.replace('"', '""') + '"'
    try:
        conn = sqlite3.connect(DATABASE_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        schema_cache = {}
        def get_info(name):
            if name not in schema_cache:
                schema_cache[name] = conn.execute(
                    f"PRAGMA table_info({quote(name)})"
                ).fetchall()

            return schema_cache[name]

        def get_columns(info):
            return [row["name"] for row in info]

        def get_pk(info):
            keys = [row for row in info if row["pk"]]

            if not keys:
                return None
            return max(keys, key=lambda row: row["pk"])["name"]
        def get_select(columns):
            return ", ".join(
                (
                    f"strftime('%Y-%m-%d %H:%M:%S', "
                    f"{quote(col)}, 'unixepoch', 'localtime') "
                    f"AS {quote(col)}"
                    if col in DATE_COLUMNS
                    else quote(col)
                )
                for col in columns
            )

        def get_record(name, columns, pk, value):
            if pk is None:
                return None

            row = conn.execute(
                f"SELECT {get_select(columns)} "
                f"FROM {quote(name)} "
                f"WHERE {quote(pk)} = ?",
                (value,)
            ).fetchone()

            return dict(row) if row else None

        def get_table_info(name):
            info = get_info(name)

            if not info:
                return None, None

            return info, get_pk(info)

        # =========================
        # GET
        # =========================
        if request.method == "GET":

            # Lightweight dashboard overview.
            if table is None:

                tables = {}

                for name in ALLOWED_TABLES:
                    info = get_info(name)

                    tables[name] = {
                        "columns": get_columns(info),
                        "count": conn.execute(
                            f"SELECT COUNT(*) FROM {quote(name)}"
                        ).fetchone()[0]
                    }

                return jsonify(tables)

            info, pk = get_table_info(table)

            if info is None:
                return jsonify({"error": "Table not found"}), 404

            columns = get_columns(info)

            # Fetch only one record when editing.
            if row_id is not None:
                if pk is None:
                    return jsonify({"error": "No primary key"}), 400

                record = get_record(table, columns, pk, row_id)

                if record is None:
                    return jsonify({"error": "Record not found"}), 404

                return jsonify(record)

            # Paginated table data.
            try:
                limit = int(request.args.get("limit", 100))
                offset = int(request.args.get("offset", 0))
            except (TypeError, ValueError):
                return jsonify({"error": "Invalid pagination"}), 400

            if limit < 1 or offset < 0:
                return jsonify({"error": "Invalid pagination"}), 400

            # Prevent excessively large responses.
            limit = min(limit, 500)

            cursor = conn.execute(
                f"SELECT {get_select(columns)} "
                f"FROM {quote(table)} "
                f"LIMIT ? OFFSET ?",
                (limit, offset)
            )

            return jsonify({
                "columns": columns,
                "rows": [list(row) for row in cursor],
                "limit": limit,
                "offset": offset
            })

        if request.method == "POST":

            if table is None:
                return jsonify({"error": "Table required"}), 400

            data = request.get_json(silent=True)

            if not isinstance(data, dict):
                return jsonify({"error": "JSON object required"}), 400

            info, pk = get_table_info(table)

            if info is None:
                return jsonify({"error": "Table not found"}), 404

            columns = get_columns(info)

            if any(col not in columns for col in data):
                return jsonify({"error": "Invalid column"}), 400

            # Allow SQLite to generate an integer primary key.
            if pk and data.get(pk) is None:
                data.pop(pk, None)

            names = list(data)

            if names:
                conn.execute(
                    f"INSERT INTO {quote(table)} "
                    f"({', '.join(quote(c) for c in names)}) "
                    f"VALUES ({', '.join('?' for _ in names)})",
                    tuple(data[c] for c in names)
                )
            else:
                conn.execute(
                    f"INSERT INTO {quote(table)} DEFAULT VALUES"
                )

            new_id = conn.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]

            conn.commit()

            return jsonify({
                "message": "Record created",
                "record": get_record(table, columns, pk, new_id)
            }), 201

        if request.method in ("PATCH", "PUT"):

            if table is None or row_id is None:
                return jsonify({
                    "error": "Table and ID required"
                }), 400

            data = request.get_json(silent=True)

            if not isinstance(data, dict) or not data:
                return jsonify({"error": "JSON object required"}), 400

            info, pk = get_table_info(table)

            if info is None:
                return jsonify({"error": "Table not found"}), 404

            columns = get_columns(info)

            if pk is None:
                return jsonify({"error": "No primary key"}), 400

            if any(col not in columns for col in data):
                return jsonify({"error": "Invalid column"}), 400

            if pk in data:
                return jsonify({
                    "error": "Cannot update primary key"
                }), 400

            # Check existence without fetching every column.
            exists = conn.execute(
                f"SELECT 1 FROM {quote(table)} "
                f"WHERE {quote(pk)} = ? LIMIT 1",
                (row_id,)
            ).fetchone()

            if not exists:
                return jsonify({"error": "Record not found"}), 404

            conn.execute(
                f"UPDATE {quote(table)} SET "
                f"{', '.join(quote(c) + ' = ?' for c in data)} "
                f"WHERE {quote(pk)} = ?",
                tuple(data.values()) + (row_id,)
            )

            conn.commit()

            return jsonify({
                "message": "Record updated",
                "record": get_record(table, columns, pk, row_id)
            })

        if request.method == "DELETE":

            if table is None or row_id is None:
                return jsonify({
                    "error": "Table and ID required"
                }), 400

            info, pk = get_table_info(table)

            if info is None:
                return jsonify({"error": "Table not found"}), 404

            if pk is None:
                return jsonify({"error": "No primary key"}), 400

            cursor = conn.execute(
                f"DELETE FROM {quote(table)} "
                f"WHERE {quote(pk)} = ?",
                (row_id,)
            )

            if cursor.rowcount == 0:
                return jsonify({"error": "Record not found"}), 404

            conn.commit()

            return jsonify({
                "message": "Record deleted",
                "id": row_id
            })

    except sqlite3.IntegrityError as e:
        if conn:
            conn.rollback()

        return jsonify({
            "error": "Database constraint failed",
            "details": str(e)
        }), 409

    except sqlite3.Error:
        if conn:
            conn.rollback()

        return jsonify({
            "error": "Database operation failed"
        }), 500

    finally:
        if conn:
            conn.close()
@app.get("/dashboard")
@admin_required
def hhg():
    return send_file(PROJECT_DIR/ "templates/dashboard.html")
@app.route("/album")
def ffdrd():
    return render_template("/album.html")
@app.route("/album-page/<name>")
def reder_alb_page(name):
    return render_template("album_page.html",name=name)
@app.route("/icon.svg")
def icon():
    return send_file(PROJECT_DIR / "icon.svg")

@app.route("/")
def f():
   return render_template("/index.html")
@app.route("/you")
def fnn():
   return render_template("/you.html")
@app.route("/login")
def login_page():
    return send_file(PROJECT_DIR /"templates/login.html")
@app.route("/logout", methods=["POST"])
def logot():
    session.clear()
    return "", 204

@app.route("/tracks")
def return_tracks():
    return render_template("tracks.html")
if __name__=="__main__":
    app.run(host="0.0.0.0",port=5000,debug=True,threaded=True)
