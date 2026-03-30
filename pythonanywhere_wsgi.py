import os
import sys


project_home = "/home/yourusername/Youtube scraping tool"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ.setdefault("FLASK_SECRET_KEY", "replace-with-a-random-secret")

from tool import app as application
