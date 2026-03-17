from playwright.sync_api import sync_playwright
import csv
from datetime import datetime
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
from bs4 import BeautifulSoup

thread_local = threading.local()


def get_browser_page():
    if not hasattr(thread_local, "page"):
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--lang=en-US",
                "--accept-lang=en-US",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York",
        )
        thread_local.page = context.new_page()
        thread_local.browser = browser
        thread_local.playwright = playwright
    return thread_local.page


def cleanup_thread():
    if hasattr(thread_local, "page"):
        thread_local.page.close()
        thread_local.browser.close()
        thread_local.playwright.stop()


def search_channels(query, limit=10):
    channels = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, args=["--lang=en-US", "--accept-lang=en-US"]
        )
        page = browser.new_page()

        search_url = f"https://www.youtube.com/results?search_query={query}"
        print(f" Searching: {search_url}")

        page.goto(search_url, timeout=30000)
        page.wait_for_timeout(3000)

        for _ in range(3):
            page.evaluate("window.scrollBy(0, 800)")
            page.wait_for_timeout(1000)

        html_content = page.content()
        soup = BeautifulSoup(html_content, "html.parser")

        channel_urls = set()

        for link in soup.find_all("a", href=True):
            href = link["href"]
            if any(x in href for x in ["/@", "/channel/", "/c/"]):
                if href.startswith("http"):
                    full_url = href
                else:
                    full_url = "https://www.youtube.com" + href

                for suffix in ["/videos", "/playlists", "/featured"]:
                    if suffix in full_url:
                        full_url = full_url.replace(suffix, "")
                        break

                channel_urls.add(full_url)

                if len(channel_urls) >= limit:
                    break

        browser.close()

        channels = list(channel_urls)[:limit]
        print(f" Found {len(channels)} channels")
        return channels


def get_channels(query, limit=10):
    try:
        return search_channels(query, limit)
    except Exception as e:
        print(f" Error in get_channels: {e}")
        return []


def scrape_channel_videos(channel_url):
    videos = []

    try:
        page = get_browser_page()
        print(f" Scraping: {channel_url}")

        videos_url = channel_url.rstrip("/") + "/videos"
        page.goto(videos_url, timeout=30000)
        page.wait_for_timeout(3000)

        print(f"  Auto-scrolling 20 times to load videos...")
        for scroll in range(20):
            page.evaluate("window.scrollBy(0, 2000)")
            page.wait_for_timeout(1500)
            if (scroll + 1) % 5 == 0:
                print(f"    Scrolled {scroll + 1}/20 times")

        html_content = page.content()
        soup = BeautifulSoup(html_content, "html.parser")
        video_items = soup.find_all("ytd-rich-item-renderer")

        if not video_items:
            video_items = soup.find_all("ytd-video-renderer")

        print(f"  Found {len(video_items)} video elements")

        for item in video_items[:80]:
            try:
                title_elem = item.find("a", {"id": "video-title"})
                if not title_elem:
                    title_elem = item.find("a", {"id": "video-title-link"})

                if not title_elem:
                    continue

                title = title_elem.get("title", "")
                if not title:
                    title = title_elem.text.strip()

                if not title:
                    continue

                video_url = title_elem.get("href", "")
                if video_url and not video_url.startswith("http"):
                    video_url = "https://www.youtube.com" + video_url

                views = ""
                upload_date = ""

                metadata_elem = item.find("div", {"id": "metadata-line"})
                if metadata_elem:
                    spans = metadata_elem.find_all("span")
                    if len(spans) >= 2:
                        views = spans[0].text.strip()
                        upload_date = spans[1].text.strip()

                if not views:
                    metadata_spans = item.find_all(
                        "span", {"class": "inline-metadata-item"}
                    )
                    if len(metadata_spans) >= 2:
                        views = metadata_spans[0].text.strip()
                        upload_date = metadata_spans[1].text.strip()
                    elif len(metadata_spans) == 1:
                        text = metadata_spans[0].text.strip()
                        parts = text.split("·")
                        if len(parts) >= 2:
                            views = parts[0].strip()
                            upload_date = parts[1].strip()

                if views and not "views" in views.lower():
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
                        duration = selector.text.strip()
                        break

                if duration:
                    duration = re.sub(r"\s+", " ", duration).strip()
                    if " " in duration:
                        duration = duration.split()[0]

                videos.append(
                    {
                        "channel_url": channel_url,
                        "video_title": title,
                        "video_url": video_url,
                        "views": views,
                        "upload_date": upload_date,
                        "duration": duration,
                    }
                )

            except Exception as e:
                continue

        print(f" Found {len(videos)} videos from this channel")
        if videos:
            print(
                f"   Sample: '{videos[0]['video_title'][:50]}...' | Views: {videos[0]['views']} | Date: {videos[0]['upload_date']} | Duration: {videos[0]['duration']}"
            )

    except Exception as e:
        print(f" Error scraping {channel_url}: {e}")

    return videos


def scrape_multiple_channels(channel_urls):
    if not channel_urls:
        print(" No channels to scrape")
        return None

    print(f"\n Starting scraper for {len(channel_urls)} channels...")
    start_time = time.time()

    all_videos = []

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(scrape_channel_videos, url) for url in channel_urls]

        for future in as_completed(futures):
            try:
                channel_videos = future.result(timeout=240)
                all_videos.extend(channel_videos)
            except Exception as e:
                print(f" Task failed: {e}")

    cleanup_thread()

    if all_videos:
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

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_videos)

        elapsed = time.time() - start_time
        print(f"\n{'='*60}")
        print(
            f" SUCCESS! Scraped {len(all_videos)} videos from {len(channel_urls)} channels"
        )
        print(f" Time taken: {elapsed:.1f} seconds")
        print(f" Saved to: {filename}")
        print(f"{'='*60}")

        print("\n Sample Data (First 3 videos):")
        for i, video in enumerate(all_videos[:3]):
            print(f"\n  {i+1}. Title: {video['video_title'][:60]}...")
            print(f"     Views: {video['views']}")
            print(f"     Date: {video['upload_date']}")
            print(f"     Duration: {video['duration']}")

        return filename
    else:
        print(" No videos found")
        return None


def get_channels_by_category(categories_input, limit=5):
    categories = [c.strip() for c in categories_input.split(",") if c.strip()]

    channels_by_category = {}

    for category in categories:
        print(f"\n Searching for: {category}")
        query = f"{category} youtube channel"
        channels = search_channels(query, limit)
        channels_by_category[category] = channels[:limit]

        print(f" {category}: {len(channels_by_category[category])} channels")

    return channels_by_category
