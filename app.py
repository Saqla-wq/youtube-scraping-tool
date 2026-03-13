from flask import Flask, render_template, request, jsonify
from scraper.video_scraper import search_channels, get_channels, scrape_channel_videos

app = Flask(__name__)

countries = [
    "United States",
    "India",
    "Brazil",
    "United Kingdom",
    "Canada",
    "Pakistan",
    "Indonesia",
    "Philippines",
    "Mexico",
    "Germany",
    "France",
    "Japan",
    "South Korea",
    "Turkey",
    "Saudi Arabia",
]


@app.route("/", methods=["GET", "POST"])
def index():
    channels = []
    youtube_link = None
    error = None

    if request.method == "POST":
        try:
            country = request.form.get("country")
            category = request.form.get("category")
            count = request.form.get("count") or 5

            query = f"{country} {category} youtube channels"
            youtube_link = f"https://www.youtube.com/results?search_query={query}"

            print(f" Searching for: {query}")
            channels = get_channels(query, int(count))
            print(f"Found {len(channels)} channels")

        except Exception as e:
            error = str(e)
            print(f"Error: {error}")

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
        return "No channels selected for scraping!"

    try:
        result = scrape_channel_videos(selected_channels)
        if result:

            return f" Scraping finished! {result}"
        else:
            return " No videos found to scrape!"
    except Exception as e:
        return f" Error during scraping: {str(e)}"


if __name__ == "__main__":
    app.run(debug=True, port=5000)
