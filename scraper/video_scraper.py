import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import os
import re
import threading
from playwright.sync_api import Error as PlaywrightError
import time
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

thread_local = threading.local()

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


def _chromium_launch_options():
    executable_path = os.environ.get("PLAYWRIGHT_EXECUTABLE_PATH")
    if not executable_path and os.environ.get("PYTHONANYWHERE_SITE"):
        executable_path = "/usr/bin/chromium"

    launch_options = {
        "headless": True,
        "args": [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--lang=en-US",
            "--accept-lang=en-US",
        ],
    }

    if executable_path:
        launch_options["executable_path"] = executable_path
        launch_options["args"] = [
            "--disable-gpu",
            "--no-sandbox",
            "--headless",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--lang=en-US",
            "--accept-lang=en-US",
        ]

    return launch_options


def get_browser_page():
    if not hasattr(thread_local, "page"):
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(**_chromium_launch_options())
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="America/New_York",
        )
        thread_local.page = context.new_page()
        thread_local.context = context
        thread_local.browser = browser
        thread_local.playwright = playwright
    return thread_local.page


def cleanup_thread():
    if hasattr(thread_local, "page"):
        thread_local.page.close()
        thread_local.context.close()
        thread_local.browser.close()
        thread_local.playwright.stop()
        del thread_local.page
        del thread_local.context
        del thread_local.browser
        del thread_local.playwright


def normalize_text(value, fallback=""):
    cleaned = re.sub(r"\s+", " ", (value or "").replace("\xa0", " ")).strip()
    return cleaned or fallback


def normalize_channel_url(url):
    if not url:
        return ""

    full_url = url if url.startswith("http") else f"https://www.youtube.com{url}"
    for suffix in ["/videos", "/featured", "/playlists", "/shorts", "/community"]:
        if suffix in full_url:
            full_url = full_url.split(suffix)[0]
    return full_url.rstrip("/")


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
        if cleaned_count < 1 or cleaned_count > 200:
            errors["count"] = "Channel count must be between 1 and 200."
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


def _extract_channel_from_renderer(renderer):
    title_link = renderer.select_one("a#main-link")
    if not title_link:
        title_link = renderer.select_one(
            "a[href*='/@'], a[href*='/channel/'], a[href*='/c/']"
        )

    channel_url = normalize_channel_url(title_link.get("href") if title_link else "")
    if not channel_url:
        return None

    channel_name = normalize_text(title_link.get("title") if title_link else "")
    if not channel_name:
        channel_name = normalize_text(
            title_link.get_text(" ", strip=True) if title_link else "",
            "Unknown channel",
        )

    subscriber_text = DEFAULT_SUBSCRIBERS
    metadata = renderer.select("#subscribers, #video-count, #metadata span")
    for item in metadata:
        text = normalize_text(item.get_text(" ", strip=True))
        if "subscriber" in text.lower():
            subscriber_text = text
            break

    description_node = renderer.select_one("#description-text")
    description = normalize_text(
        description_node.get_text(" ", strip=True) if description_node else "",
        DEFAULT_CHANNEL_DESCRIPTION,
    )

    return {
        "channel_name": channel_name,
        "channel_url": channel_url,
        "subscribers": subscriber_text,
        "description": description,
    }


def _extract_channels_from_anchors(soup, limit, category, country_name):
    discovered = []
    seen_urls = set()

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not any(marker in href for marker in ["/@", "/channel/", "/c/"]):
            continue

        channel_url = normalize_channel_url(href)
        if not channel_url or channel_url in seen_urls:
            continue

        channel_name = normalize_text(
            link.get("title") or link.get_text(" ", strip=True), "Unknown channel"
        )
        discovered.append(
            {
                "channel_name": channel_name,
                "channel_url": channel_url,
                "subscribers": DEFAULT_SUBSCRIBERS,
                "description": f"{category} channel discovered for {country_name}",
            }
        )
        seen_urls.add(channel_url)

        if len(discovered) >= limit:
            break

    return discovered


def search_channels(query, limit=10, country_name="", category=""):
    channels = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**_chromium_launch_options())
        context = browser.new_context(locale="en-US")
        page = context.new_page()

        search_url = (
            "https://www.youtube.com/results"
            f"?search_query={quote_plus(query)}&sp=EgIQAg%253D%253D"
        )
        print(f"Searching: {search_url}")

        try:
            page.goto(search_url, timeout=45000, wait_until="domcontentloaded")
        except PlaywrightError as e:
            print(f"Playwright failed for {search_url}: {e}")
            return []

        page.wait_for_timeout(3500)

        for _ in range(4):
            page.evaluate("window.scrollBy(0, 1000)")
            page.wait_for_timeout(1200)

        soup = BeautifulSoup(page.content(), "html.parser")
        seen_urls = set()

        for renderer in soup.find_all("ytd-channel-renderer"):
            channel = _extract_channel_from_renderer(renderer)
            if not channel:
                continue

            if channel["channel_url"] in seen_urls:
                continue

            seen_urls.add(channel["channel_url"])
            channels.append(channel)

            if len(channels) >= limit:
                break

        if not channels:
            channels = _extract_channels_from_anchors(
                soup, limit, category, country_name
            )

        context.close()
        browser.close()

    print(f"Found {len(channels)} channels")
    return channels[:limit]


def scrape_channel_videos(channel_url):
    videos = []

    try:
        page = get_browser_page()
        print(f"Scraping: {channel_url}")

        videos_url = channel_url.rstrip("/") + "/videos"
        page.goto(videos_url, timeout=30000)
        page.wait_for_timeout(3000)

        for _ in range(8):
            page.evaluate("window.scrollBy(0, 2000)")
            page.wait_for_timeout(1500)

        html_content = page.content()
        soup = BeautifulSoup(html_content, "html.parser")
        video_items = soup.find_all("ytd-rich-item-renderer") or soup.find_all(
            "ytd-video-renderer"
        )

        for item in video_items[:30]:
            try:
                title_elem = item.find("a", {"id": "video-title"}) or item.find(
                    "a", {"id": "video-title-link"}
                )
                if not title_elem:
                    continue

                title = normalize_text(
                    title_elem.get("title") or title_elem.get_text(" ", strip=True)
                )
                if not title:
                    continue

                href = title_elem.get("href", "")
                video_url = (
                    href
                    if href.startswith("http")
                    else f"https://www.youtube.com{href}"
                )

                views = ""
                upload_date = ""

                metadata_elem = item.find("div", {"id": "metadata-line"})
                if metadata_elem:
                    spans = metadata_elem.find_all("span")
                    if len(spans) >= 2:
                        views = normalize_text(spans[0].text)
                        upload_date = normalize_text(spans[1].text)

                if not views:
                    metadata_spans = item.find_all(
                        "span", {"class": "inline-metadata-item"}
                    )
                    if len(metadata_spans) >= 2:
                        views = normalize_text(metadata_spans[0].text)
                        upload_date = normalize_text(metadata_spans[1].text)

                if views and "views" not in views.lower():
                    num_match = re.search(r"([\d,.]+[KMB]?)", views)
                    if num_match:
                        views = f"{num_match.group(1)} views"

                duration = ""
                duration_selectors = [
                    item.find(
                        "span", {"class": "ytd-thumbnail-overlay-time-status-renderer"}
                    ),
                    item.find("ytd-thumbnail-overlay-time-status-renderer"),
                    item.find("span", {"class": "badge-shape-wiz__text"}),
                ]

                for selector in duration_selectors:
                    if selector:
                        duration = normalize_text(selector.text)
                        break

                videos.append(
                    {
                        "channel_url": channel_url,
                        "video_title": title,
                        "video_url": video_url,
                        "views": views or "Views unavailable",
                        "upload_date": upload_date or "Date unavailable",
                        "duration": duration or "Duration unavailable",
                    }
                )
            except Exception:
                continue

    except Exception as exc:
        print(f"Error scraping {channel_url}: {exc}")
    finally:
        cleanup_thread()

    return videos


def scrape_multiple_channels(channel_urls):
    if not channel_urls:
        print("No channels to scrape")
        return None

    start_time = time.time()
    all_videos = []

    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = [executor.submit(scrape_channel_videos, url) for url in channel_urls]
        for future in as_completed(futures):
            try:
                channel_videos = future.result(timeout=240)
                all_videos.extend(channel_videos)
            except Exception as exc:
                print(f"Task failed: {exc}")

    if not all_videos:
        print("No videos found")
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

    elapsed = time.time() - start_time
    print(
        f"Scraped {len(all_videos)} videos from {len(channel_urls)} channels in {elapsed:.1f} seconds"
    )
    print(f"Saved to: {filename}")
    return filename
