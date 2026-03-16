from flask import Flask, render_template, request, redirect, url_for, send_file
from scraper.video_scraper import get_channels, scrape_multiple_channels
import os, io, datetime
import uuid
import csv
from collections import defaultdict

app = Flask(__name__)

countries = [
    "United States",
    "India",
    "Pakistan",
    "United Kingdom",
    "Canada",
    "Australia",
    "Germany",
    "France",
    "Japan",
    "South Korea",
    "Brazil",
    "Mexico",
    "Indonesia",
    "Turkey",
    "Saudi Arabia",
]
results_cache = {}


@app.route("/", methods=["GET", "POST"])
def index():
    channels = []
    error = None
    youtube_link = None

    if request.method == "POST":
        country = request.form.get("country")
        category = request.form.get("category")
        count = int(request.form.get("count", 5))

        query = f"{country} {category} youtube channels"
        youtube_link = f"https://www.youtube.com/results?search_query={query}"

        try:
            channels = get_channels(query, count)
            print(f"Found channels: {channels}")
        except Exception as e:
            error = str(e)
            print(f"Error: {e}")

    return render_template(
        "index.html",
        countries=countries,
        channels=channels,
        youtube_link=youtube_link,
        error=error,
    )


@app.route("/scrape", methods=["POST"])
def scrape():
    selected_channels = request.form.getlist("channels")

    if not selected_channels:
        return "Please select at least one channel"

    try:
        print(f"Selected channels: {selected_channels}")
        filename = scrape_multiple_channels(selected_channels)

        if filename:
            session_id = str(uuid.uuid4())[:8]
            results_cache[session_id] = filename

            return redirect(url_for("success", session_id=session_id))
        else:
            return "No videos found to scrape"

    except Exception as e:
        print(f"Scrape error: {e}")
        return f"Error: {str(e)}"


@app.route("/success")
def success():
    session_id = request.args.get("session_id")
    filename = results_cache.get(session_id)

    if not filename or not os.path.exists(filename):
        return "File not found"

    videos_by_channel = defaultdict(list)
    total_videos = 0

    try:
        with open(filename, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                channel = row.get("channel_url", "Unknown Channel")
                video_data = {
                    "video_title": row.get("video_title", "No Title"),
                    "views": row.get("views", ""),
                    "upload_date": row.get("upload_date", ""),
                    "duration": row.get("duration", ""),
                    "url": row.get("video_url", "#"),
                }
                videos_by_channel[channel].append(video_data)
                total_videos += 1
    except Exception as e:
        print(f"Error reading CSV: {e}")

    return render_template(
        "success.html",
        filename=os.path.basename(filename),
        session_id=session_id,
        videos_by_channel=dict(videos_by_channel),
        total_videos=total_videos,
    )


@app.route("/download/<session_id>")
def download(session_id):
    filename = results_cache.get(session_id)
    if not filename or not os.path.exists(filename):
        return "File not found"
    return send_file(
        filename,
        as_attachment=True,
        download_name=os.path.basename(filename),
        mimetype="text/csv",
    )


@app.route("/")
def home():
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
