from playwright.sync_api import sync_playwright
import time
import csv
from datetime import datetime


def search_channels(query, limit=10):
    channels = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 800})
        search_url = f"https://www.youtube.com/results?search_query={query}"
        print(f" Searching: {search_url}")

        page.goto(search_url, timeout=60000)
        page.wait_for_timeout(5000)
        for i in range(5):
            page.evaluate("window.scrollBy(0, 1000)")
            print(f" Scrolling... ({i+1}/5)")
            page.wait_for_timeout(3000)
        selectors = [
            "a.ytd-channel-name",
            "a#video-title",
            "ytd-channel-renderer a",
            "a.ytd-video-renderer",
            "a[href*='/channel/']",
            "a[href*='/c/']",
            "a[href*='/@']",
        ]

        channel_urls = set()

        for selector in selectors:
            try:
                elements = page.locator(selector).all()
                print(f"🔎 Selector '{selector}' found {len(elements)} elements")

                for element in elements:
                    href = element.get_attribute("href")
                    if href:
                        if any(x in href for x in ["/channel/", "/c/", "/@", "/user/"]):
                            if href.startswith("http"):
                                full_link = href
                            else:
                                full_link = "https://www.youtube.com" + href
                            channel_urls.add(full_link)
                            print(f" Found channel: {full_link}")
            except Exception as e:
                print(f" Error with selector {selector}: {str(e)}")
                continue

        channels = list(channel_urls)[:limit]
        if not channels:
            print(" No channels found with selectors, trying alternative method...")
            all_links = page.locator("a").all()
            for link in all_links:
                href = link.get_attribute("href")
                if href and any(
                    x in href for x in ["/channel/", "/c/", "/@", "/user/"]
                ):
                    if href.startswith("http"):
                        full_link = href
                    else:
                        full_link = "https://www.youtube.com" + href
                    channels.append(full_link)
                    if len(channels) >= limit:
                        break

        browser.close()

        print(f"\n Total channels found: {len(channels)}")
        return channels


def get_channels(query, limit=10):
    try:
        return search_channels(query, limit)
    except Exception as e:
        print(f" Error in get_channels: {str(e)}")
        return []


def scrape_channel_videos(channel_urls):
    if isinstance(channel_urls, str):
        channel_urls = [channel_urls]

    all_videos = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 800})

        for channel_url in channel_urls:
            print(f"\n Scraping channel: {channel_url}")

            if channel_url.endswith("/"):
                videos_url = channel_url + "videos"
            else:
                videos_url = channel_url + "/videos"

            try:
                print(f" Navigating to: {videos_url}")
                page.goto(videos_url, timeout=60000)
                page.wait_for_timeout(5000)

                for i in range(5):
                    page.evaluate("window.scrollBy(0, 1000)")
                    print(f" Scrolling for videos... ({i+1}/5)")
                    page.wait_for_timeout(2000)

                video_selectors = [
                    "a#video-title",
                    "ytd-video-renderer a#video-title",
                    "a.ytd-video-renderer",
                    "a[href*='/watch']",
                ]

                channel_videos = []
                video_urls = set()

                for selector in video_selectors:
                    videos = page.locator(selector).all()
                    for video in videos:
                        if len(channel_videos) >= 20:
                            break

                        href = video.get_attribute("href")
                        title = video.get_attribute("title") or video.text_content()

                        if href and "/watch" in href:
                            if href.startswith("http"):
                                video_url = href
                            else:
                                video_url = "https://www.youtube.com" + href

                            if video_url not in video_urls:
                                video_urls.add(video_url)
                                channel_videos.append(
                                    {
                                        "channel": channel_url,
                                        "title": title.strip() if title else "No Title",
                                        "url": video_url,
                                    }
                                )
                                print(f" Found video: {title[:50]}...")

                all_videos.extend(channel_videos)
                print(f" Found {len(channel_videos)} videos from {channel_url}")

            except Exception as e:
                print(f" Error scraping {channel_url}: {str(e)}")
                continue

        browser.close()

    if all_videos:
        filename = f"youtube_videos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        with open(filename, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["channel", "title", "url"])
            writer.writeheader()
            writer.writerows(all_videos)

        print(f"\n Saved {len(all_videos)} videos to {filename}")
        return filename
    else:
        print("No videos found")
        return None
