from playwright.sync_api import sync_playwright
import csv


def scroll_page(page):
    for _ in range(8):
        page.mouse.wheel(0, 5000)
        page.wait_for_timeout(2000)


def handle_consent(page):
    if "consent.youtube.com" in page.url:
        try:
            page.click('button:has-text("Accept all")', timeout=5000)
            page.wait_for_load_state("networkidle")
        except:
            pass


def scrape_channels(channels):
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir="youtube_session", headless=False
        )

        page = context.new_page()
        with open("youtube_videos.csv", "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)

            for channel in channels:
                print("\nOpening:", channel)
                page.goto(channel)
                handle_consent(page)
                page.wait_for_selector("ytd-rich-grid-media")
                channel_name = page.locator("ytd-channel-name").first.inner_text()
                scroll_page(page)
                videos = page.locator("ytd-rich-grid-media")
                count = videos.count()
                print("Videos found:", count)

                writer.writerow([f"{channel_name}"])
                writer.writerow(["Title", "Views", "Upload Date"])

                for i in range(count):
                    video = videos.nth(i)
                    title = video.locator("#video-title").inner_text()
                    views = video.locator("#metadata-line span").first.inner_text()
                    upload_date = (
                        video.locator("#metadata-line span").nth(1).inner_text()
                    )
                    print(title, views, upload_date)

                    writer.writerow([title, views, upload_date])

                writer.writerow([])

        context.close()
