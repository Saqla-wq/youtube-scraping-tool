from flask import Flask, render_template, request
from scraper.video_scraper import scrape_channels
import webbrowser

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

categories = [
    "Entertainment",
    "News",
    "Music",
    "Gaming",
    "Sports",
    "Education",
    "Technology",
    "Kids",
    "Islamic",
]


@app.route("/", methods=["GET", "POST"])
def index():
    youtube_link = None

    if request.method == "POST":
        country = request.form["country"]
        category = request.form["category"]
        query = f"{country} {category} youtube channels"
        youtube_link = f"https://www.youtube.com/results?search_query={query}"
        webbrowser.open(youtube_link)

    return render_template(
        "index.html",
        countries=countries,
        categories=categories,
        youtube_link=youtube_link,
    )


@app.route("/scrape", methods=["POST"])
def scrape():
    channels = request.form.get("channels")
    channel_list = [c.strip() for c in channels.split("\n") if c.strip()]
    scrape_channels(channel_list)
    return "Scraping finished. CSV file saved."


if __name__ == "__main__":
    app.run(debug=True)
