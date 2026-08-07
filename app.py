from flask import Flask, request, jsonify, send_file
import yt_dlp
import requests
import os
import tempfile

app = Flask(__name__)
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

@app.route("/")
def home():
    return jsonify({"status": "online", "message": "Pro Video API is running"})

@app.route("/search")
def search():
    query = request.args.get("q", "Bangla new songs")
    page_token = request.args.get("pageToken", "")

    if not YOUTUBE_API_KEY:
        return jsonify({"error": "YOUTUBE_API_KEY is not configured"}), 500

    params = {
        "part": "snippet",
        "maxResults": 12,
        "q": query,
        "type": "video",
        "pageToken": page_token,
        "key": YOUTUBE_API_KEY
    }

    try:
        response = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params=params,
            timeout=15
        )
        data = response.json()

        if response.status_code != 200:
            return jsonify({
                "error": data.get("error", {}).get("message", "YouTube API error"),
                "videos": [],
                "nextPageToken": ""
            }), response.status_code

        videos = []
        for item in data.get("items", []):
            video_id = item["id"]["videoId"]
            videos.append({
                "title": item["snippet"]["title"],
                "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
                "url": f"https://www.youtube.com/watch?v={video_id}"
            })

        return jsonify({
            "videos": videos,
            "nextPageToken": data.get("nextPageToken", "")
        })
    except Exception as e:
        return jsonify({"error": str(e), "videos": [], "nextPageToken": ""}), 500

@app.route("/get_info", methods=["POST"])
def get_info():
    data = request.get_json(silent=True) or {}
    video_url = data.get("url")

    if not video_url:
        return jsonify({"error": "Video URL is required"}), 400

    ydl_opts = {
        "quiet": True,
        "noplaylist": True,
        "skip_download": True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            formats = info.get("formats", [])
            play_url = None

            # Prefer a combined MP4 stream that has both video and audio.
            for f in formats:
                if (
                    f.get("vcodec") != "none"
                    and f.get("acodec") != "none"
                    and f.get("ext") == "mp4"
                ):
                    play_url = f.get("url")
                    break

            if not play_url:
                play_url = info.get("url")

            return jsonify({
                "title": info.get("title", "Unknown"),
                "thumbnail": info.get("thumbnail"),
                "video_url": play_url,
                "url": video_url
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download")
def download():
    video_url = request.args.get("url")
    quality = request.args.get("quality", "720p")

    if not video_url:
        return jsonify({"error": "Video URL is required"}), 400

    quality_map = {
        "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]",
        "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]",
        "mp3": "bestaudio/best"
    }

    selected_format = quality_map.get(quality, quality_map["720p"])
    temp_dir = tempfile.mkdtemp()
    output_template = os.path.join(temp_dir, "%(title)s.%(ext)s")

    ydl_opts = {
        "format": selected_format,
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True
    }

    if quality == "mp3":
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192"
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)

            if quality == "mp3":
                filename = os.path.splitext(filename)[0] + ".mp3"

            return send_file(
                filename,
                as_attachment=True,
                download_name=os.path.basename(filename)
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
