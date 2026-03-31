#!/bin/bash

echo "Installing Playwright browsers..."
playwright install --with-deps

echo "Starting app..."
gunicorn app:app --bind 0.0.0.0:$PORT