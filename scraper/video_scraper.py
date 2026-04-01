import csv
from datetime import datetime
import os
import re

import requests

COUNTRIES = [
    {"code": "US", "name": "United States"},
    {"code": "IN", "name": "India"},
    {"code": "PK", "name": "Pakistan"},
    {"code": "GB", "name": "United Kingdom"},
    {"code": "CA", "name": "Canada"},
    {"code": "AU", "name": "Australia"},
    {"code": "DE", "name": "Germany"},
    {"code": "FR", "name": "France"},
    {"code": "JP", "name": "Japan"},
    {"code": "KR", "name": "South Korea"},
    {"code": "BR", "name": "Brazil"},
    {"code": "MX", "name": "Mexico"},
    {"code": "ID", "name": "Indonesia"},
    {"code": "TR", "name": "Turkey"},
    {"code": "SA", "name": "Saudi Arabia"},
]

COUNTRY_MAP = {country["code"]: country["name"] for country in COUNTRIES}
DEFAULT_CHANNEL_DESCRIPTION = "Description unavailable"
DEFAULT_SUBSCRIBERS = "Subscribers unavailable"
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()


def extract_channel_id(value):
    value = (value or "").strip()
    if not value:
        return ""

    if value.startswith("http"):
        return value.rstrip("/").split("/")[-1]

    return value


def normalize_text(value, fallback=""):
    cleaned = re.sub(r"\s+", " ", (value or "").replace("\xa0", " ")).strip()
    return cleaned or fallback


def parse_categories(categories_input):
    categories = []
    for raw in (categories_input or "").split(","):
        cleaned = normalize_text(raw)
        if cleaned:
            categories.append(cleaned)
    return categories


def validate_search_inputs(country_code, categories_input, count_value):
    errors = {}
    cleaned_country = (country_code or "").strip().upper()
    categories = parse_categories(categories_input)

    if cleaned_country not in COUNTRY_MAP:
        errors["country"] = "Please choose a valid country."

    if not categories:
        errors["category"] = "Please enter at least one category."
    else:
        too_short = [cat for cat in categories if len(cat) < 2]
        if too_short:
            errors["category"] = "Each category must be at least 2 characters long."

    try:
        cleaned_count = int(str(count_value).strip())
        if cleaned_count < 1 or cleaned_count > 50:
            errors["count"] = "Channel count must be between 1 and 50."
    except (TypeError, ValueError):
        cleaned_count = None
        errors["count"] = "Please enter a whole number for channel count."

    cleaned = {
        "country_code": cleaned_country,
        "country_name": COUNTRY_MAP.get(cleaned_country, ""),
        "categories": categories,
        "count": cleaned_count,
    }
    return errors, cleaned


def build_search_query(country_name, category):
    return f"{category} youtube channels in {country_name}"


def _api_get(path, params):
    if not YOUTUBE_API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY is not set")

    query = dict(params)
    query["key"] = YOUTUBE_API_KEY

    response = requests.get(f"{YOUTUBE_API_BASE}/{path}", params=query, timeout=30)
    response.raise_for_status()
    return response.json()


def _format_subscribers(count):
    try:
        count_int = int(count)
    except (TypeError, ValueError):
        return DEFAULT_SUBSCRIBERS

    if count_int >= 1_000_000:
        return f"{count_int / 1_000_000:.1f}M subscribers"
    if count_int >= 1_000:
        return f"{count_int / 1_000:.1f}K subscribers"
    return f"{count_int} subscribers"


def search_channels(query, limit=10, country_name="", category=""):
    search_data = _api_get(
        "search",
        {
            "part": "snippet",
            "q": query,
            "type": "channel",
            "maxResults": min(limit, 25),
        },
    )

    channel_ids = []
    for item in search_data.get("items", []):
        snippet = item.get("snippet", {})
        channel_id = snippet.get("channelId")
        if channel_id and channel_id not in channel_ids:
            channel_ids.append(channel_id)

    if not channel_ids:
        return []

    channels_data = _api_get(
        "channels",
        {
            "part": "snippet,statistics",
            "id": ",".join(channel_ids),
        },
    )

    channels = []
    for item in channels_data.get("items", []):
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})
        channel_id = item.get("id", "")

        channels.append(
            {
                "channel_id": channel_id,
                "channel_name": snippet.get("title", "Unknown channel"),
                "channel_url": f"https://www.youtube.com/channel/{channel_id}",
                "subscribers": _format_subscribers(statistics.get("subscriberCount")),
                "description": normalize_text(
                    snippet.get("description"),
                    f"{category} channel discovered for {country_name}",
                ),
            }
        )

    return channels[:limit]


def discover_channels(country_code, category, limit=5):
    country_name = COUNTRY_MAP[country_code]
    query = build_search_query(country_name, category)
    return search_channels(
        query=query,
        limit=limit,
        country_name=country_name,
        category=category,
    )


def discover_channels_by_categories(country_code, categories, limit=5):
    country_name = COUNTRY_MAP[country_code]
    channels_by_category = {}
    for category in categories:
        query = build_search_query(country_name, category)
        channels_by_category[category] = search_channels(
            query=query,
            limit=limit,
            country_name=country_name,
            category=category,
        )
    return channels_by_category


def _fetch_video_details(video_ids):
    if not video_ids:
        return {}

    details_data = _api_get(
        "videos",
        {
            "part": "contentDetails,statistics",
            "id": ",".join(video_ids),
        },
    )

    details_map = {}
    for item in details_data.get("items", []):
        details_map[item.get("id")] = {
            "views": item.get("statistics", {}).get("viewCount"),
            "duration": item.get("contentDetails", {}).get("duration"),
        }
    return details_map


def _format_views(view_count):
    try:
        return f"{int(view_count):,} views"
    except (TypeError, ValueError):
        return "Views unavailable"


def scrape_channel_videos(channel_value):
    channel_id = extract_channel_id(channel_value)
    if not channel_id:
        return []

    data = _api_get(
        "search",
        {
            "part": "snippet",
            "channelId": channel_id,
            "order": "date",
            "type": "video",
            "maxResults": 30,
        },
    )
    video_ids = []
    items = []
    for item in data.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        if video_id:
            video_ids.append(video_id)
            items.append(item)

    details_map = _fetch_video_details(video_ids)
    videos = []

    for item in items:
        snippet = item.get("snippet", {})
        video_id = item.get("id", {}).get("videoId")
        details = details_map.get(video_id, {})

        videos.append(
            {
                "channel_url": f"https://www.youtube.com/channel/{channel_id}",
                "video_title": snippet.get("title") or "No title available",
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
                "views": _format_views(details.get("views")),
                "upload_date": snippet.get("publishedAt", "Date unavailable"),
                "duration": details.get("duration") or "Duration unavailable",
            }
        )

    return videos


def scrape_multiple_channels(channel_ids):
    if not channel_ids:
        return None

    all_videos = []
    for channel_id in channel_ids:
        try:
            all_videos.extend(scrape_channel_videos(channel_id))
        except Exception as exc:
            print(f"Task failed for {channel_id}: {exc}")

    if not all_videos:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"youtube_videos_{timestamp}.csv"
    fieldnames = [
        "channel_url",
        "video_title",
        "video_url",
        "views",
        "upload_date",
        "duration",
    ]

    with open(filename, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_videos)

    return filename
