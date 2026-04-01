#!/bin/bash

echo "Installing Playwright browsers..."
pip install -r requirements.txt && playwright install --with-deps chromium

#!/bin/bash
echo "Starting app..."
gunicorn app:app --bind 0.0.0.0:$PORT --log-level debug --access-logfile - --error-logfile -
