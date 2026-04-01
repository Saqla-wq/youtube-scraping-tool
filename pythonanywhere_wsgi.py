import os
import sys


PROJECT_HOME = "/home/yourusername/youtube-scraping-tool"

if PROJECT_HOME not in sys.path:
    sys.path.insert(0, PROJECT_HOME)

os.environ.setdefault("PLAYWRIGHT_EXECUTABLE_PATH", "/usr/bin/chromium")

from app import app as application
