import csv
import os
import uuid
from collections import defaultdict
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename
from yt_dlp import YoutubeDL

from scraper.video_scraper import (
    COUNTRIES,
    discover_channels_by_categories,
    scrape_multiple_channels,
    validate_search_inputs,
)


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = DATA_DIR / "results"
DOWNLOADS_DIR = DATA_DIR / "temp_downloads"


def ensure_directories():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)


def create_app():
    ensure_directories()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get(
        "FLASK_SECRET_KEY", "change-this-secret-key-before-production"
    )
    app.config["RESULTS_DIR"] = RESULTS_DIR
    app.config["DOWNLOADS_DIR"] = DOWNLOADS_DIR

    register_routes(app)
    return app


def _safe_file_path(base_dir: Path, filename: str) -> Path:
    cleaned_name = secure_filename(filename)
    if not cleaned_name:
        abort(404)

    candidate = (base_dir / cleaned_name).resolve()
    base_resolved = base_dir.resolve()
    if base_resolved not in candidate.parents and candidate != base_resolved:
        abort(404)
    return candidate


def register_routes(app):
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
                except Exception as exc:
                    app.logger.exception("Channel discovery failed")
                    errors["general"] = (
                        "Search failed on the server. "
                        "On PythonAnywhere this is usually caused by Chromium setup, "
                        "Playwright browser access, or account network restrictions. "
                        f"Details: {exc}"
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
            return "Please select at least one channel.", 400

        try:
            filename = scrape_multiple_channels(
                selected_channels,
                output_dir=app.config["RESULTS_DIR"],
            )
            if not filename:
                return "No videos were found for the selected channels.", 404

            result_name = Path(filename).name
            result_token = uuid.uuid4().hex[:8]
            return redirect(
                url_for(
                    "success",
                    result_token=result_token,
                    filename=result_name,
                )
            )
        except Exception as exc:
            app.logger.exception("Scrape error")
            return f"Error: {exc}", 500

    @app.route("/success")
    def success():
        filename = request.args.get("filename", "")
        file_path = _safe_file_path(app.config["RESULTS_DIR"], filename)

        if not file_path.exists():
            return "File not found.", 404

        videos_by_channel = defaultdict(list)
        total_videos = 0

        try:
            with file_path.open("r", encoding="utf-8") as handle:
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
        except Exception:
            app.logger.exception("Error reading CSV")

        return render_template(
            "success.html",
            filename=file_path.name,
            result_token=request.args.get("result_token", ""),
            videos_by_channel=dict(videos_by_channel),
            total_videos=total_videos,
        )

    @app.route("/download/results/<filename>")
    def download_results(filename):
        file_path = _safe_file_path(app.config["RESULTS_DIR"], filename)
        if not file_path.exists():
            return "File not found.", 404

        return send_file(
            file_path,
            as_attachment=True,
            download_name=file_path.name,
            mimetype="text/csv",
        )

    @app.route("/download/video")
    def download_video():
        video_url = (request.args.get("url") or "").strip()
        if not video_url:
            return "Missing video URL.", 400

        output_path = app.config["DOWNLOADS_DIR"]
        ydl_opts = {
            "outtmpl": str(output_path / "%(title)s.%(ext)s"),
            "format": "best[height<=720]",
            "noplaylist": True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            file_name = ydl.prepare_filename(info)

        return send_file(file_name, as_attachment=True)


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
