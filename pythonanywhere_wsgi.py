import os
import sys


project_home = "/home/yourusername/Youtube scraping tool"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ.setdefault("FLASK_SECRET_KEY", "replace-with-a-random-secret")
os.environ.setdefault("CHROMIUM_EXECUTABLE_PATH", "/usr/bin/chromium")

from tool import app as application
