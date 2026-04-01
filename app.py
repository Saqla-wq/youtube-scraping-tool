from collections import defaultdict
import csv
from yt_dlp import YoutubeDL
import os
import uuid
from flask import Flask, redirect, render_template, request, send_file, url_for

from scraper.video_scraper import (
    COUNTRIES,
    discover_channels_by_categories,
    scrape_multiple_channels,
    validate_search_inputs,
)


app = Flask(__name__)

results_cache = {}


@app.route("/", methods=["GET", "POST"])
def index():
    form_data = {
        "country": COUNTRIES[0]["code"],
        "category": "",
        "count": "5",
    }
    errors = {}
    channels_by_category = {}
    summary = None

    if request.method == "POST":
        form_data = {
            "country": (request.form.get("country") or "").strip().upper(),
            "category": (request.form.get("category") or "").strip(),
            "count": (request.form.get("count") or "").strip(),
        }

        errors, cleaned = validate_search_inputs(
            country_code=form_data["country"],
            categories_input=form_data["category"],
            count_value=form_data["count"],
        )

        if not errors:
            try:
                channels_by_category = discover_channels_by_categories(
                    country_code=cleaned["country_code"],
                    categories=cleaned["categories"],
                    limit=cleaned["count"],
                )
            except Exception as e:
                app.logger.exception("Search failed")
                channels_by_category = {}
                errors.append(
                    "Search is temporarily unavailable right now. Please try again later."
                )

            total_returned = sum(
                len(category_channels)
                for category_channels in channels_by_category.values()
            )
            total_requested = cleaned["count"] * len(cleaned["categories"])
            summary = {
                "country_name": cleaned["country_name"],
                "categories": cleaned["categories"],
                "requested_count": total_requested,
                "returned_count": total_returned,
                "per_category": cleaned["count"],
            }

            if not total_returned:
                errors["general"] = (
                    "No channels were found for that country and category. "
                    "Try a broader category or a smaller count."
                )

    return render_template(
        "index.html",
        countries=COUNTRIES,
        form_data=form_data,
        errors=errors,
        channels_by_category=channels_by_category,
        summary=summary,
    )


@app.route("/scrape", methods=["POST"])
def scrape():
    selected_channels = request.form.getlist("channels")
    if not selected_channels:
        return "Please select at least one channel."

    try:
        filename = scrape_multiple_channels(selected_channels)
        if not filename:
            return "No videos were found for the selected channels."

        session_id = str(uuid.uuid4())[:8]
        results_cache[session_id] = filename
        return redirect(url_for("success", session_id=session_id))
    except Exception as exc:
        print(f"Scrape error: {exc}")
        return f"Error: {exc}"


@app.route("/success")
def success():
    session_id = request.args.get("session_id")
    filename = results_cache.get(session_id)

    if not filename or not os.path.exists(filename):
        return "File not found."

    videos_by_channel = defaultdict(list)
    total_videos = 0

    try:
        with open(filename, "r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                channel = row.get("channel_url") or "Unknown Channel"
                video_data = {
                    "video_title": row.get("video_title") or "No title available",
                    "views": row.get("views") or "Views unavailable",
                    "upload_date": row.get("upload_date") or "Date unavailable",
                    "duration": row.get("duration") or "Duration unavailable",
                    "url": row.get("video_url") or "#",
                }
                videos_by_channel[channel].append(video_data)
                total_videos += 1
    except Exception as exc:
        print(f"Error reading CSV: {exc}")

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
        return "File not found."

    return send_file(
        filename,
        as_attachment=True,
        download_name=os.path.basename(filename),
        mimetype="text/csv",
    )


@app.route("/download")
def download_video():
    video_url = request.args.get("url")
    output_path = os.path.join(os.getcwd(), "temp_downloads")
    os.makedirs(output_path, exist_ok=True)

    ydl_opts = {
        "outtmpl": os.path.join(output_path, "%(title)s.%(ext)s"),
        "format": "best[height<=720]",  # keep smaller for browser download
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        file_name = ydl.prepare_filename(info)
    return send_file(file_name, as_attachment=True)


@app.route("/health")
def health():
    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
