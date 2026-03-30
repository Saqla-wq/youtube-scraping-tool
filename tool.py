import os

import requests
from flask import Flask, render_template, request


YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get(
        "FLASK_SECRET_KEY", "change-this-secret-key-before-production"
    )
    app.config["YOUTUBE_API_KEY"] = os.environ.get("YOUTUBE_API_KEY", "").strip()

    register_routes(app)
    return app


def search_youtube(query: str, api_key: str, max_results: int = 12):
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "key": api_key,
    }

    response = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=20)
    response.raise_for_status()

    payload = response.json()
    results = []

    for item in payload.get("items", []):
        video_id = (item.get("id") or {}).get("videoId")
        snippet = item.get("snippet") or {}
        if not video_id:
            continue

        results.append(
            {
                "title": snippet.get("title") or "Untitled video",
                "channel_title": snippet.get("channelTitle") or "Unknown channel",
                "description": snippet.get("description") or "No description available.",
                "thumbnail": (
                    (snippet.get("thumbnails") or {})
                    .get("medium", {})
                    .get("url", "")
                ),
                "published_at": snippet.get("publishedAt") or "",
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
            }
        )

    return results


def register_routes(app):
    @app.route("/", methods=["GET"])
    def index():
        return render_template(
            "index.html",
            query="",
            results=[],
            errors={},
        )

    @app.route("/search", methods=["POST"])
    def search():
        query = (request.form.get("query") or "").strip()
        errors = {}
        results = []

        if not query:
            errors["query"] = "Please enter something to search for."
            return render_template(
                "index.html",
                query=query,
                results=results,
                errors=errors,
            )

        api_key = app.config.get("YOUTUBE_API_KEY", "")
        if not api_key:
            errors["general"] = (
                "The YouTube API key is missing. "
                "Set the YOUTUBE_API_KEY environment variable on PythonAnywhere."
            )
            return render_template(
                "index.html",
                query=query,
                results=results,
                errors=errors,
            )

        try:
            results = search_youtube(query=query, api_key=api_key)
            if not results:
                errors["general"] = "No YouTube results were found for that search."
        except requests.exceptions.HTTPError as exc:
            app.logger.exception("YouTube API HTTP error")
            api_message = ""
            try:
                error_payload = exc.response.json()
                api_message = (
                    ((error_payload.get("error") or {}).get("message")) or ""
                ).strip()
            except ValueError:
                api_message = ""

            errors["general"] = (
                "The YouTube API request failed."
                + (f" Details: {api_message}" if api_message else "")
            )
        except requests.exceptions.RequestException as exc:
            app.logger.exception("YouTube API network error")
            errors["general"] = (
                "The server could not reach the YouTube API. "
                f"Details: {exc}"
            )
        except Exception as exc:
            app.logger.exception("Unexpected search error")
            errors["general"] = f"Unexpected error: {exc}"

        return render_template(
            "index.html",
            query=query,
            results=results,
            errors=errors,
        )


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
