# PythonAnywhere deployment guide

## Important note

This project uses Flask plus Playwright/Chromium to scrape YouTube.
For PythonAnywhere, that means:

- Flask hosting works well.
- The scraper should be used on a paid PythonAnywhere plan for practical use.
- You should use PythonAnywhere's built-in Chromium instead of trying to install a browser manually.

## 1. Upload the project

Upload this project folder to:

`/home/yourusername/Youtube scraping tool`

## 2. Create a virtualenv

Open a Bash console on PythonAnywhere and run:

```bash
mkvirtualenv --python=/usr/bin/python3.13 yt-scraper-env
workon yt-scraper-env
pip install -r "/home/yourusername/Youtube scraping tool/requirements.txt"
```

## 3. Create the web app

In the PythonAnywhere Web tab:

1. Add a new web app
2. Choose `Manual configuration`
3. Pick the same Python version as your virtualenv
4. Set the virtualenv to:

```text
/home/yourusername/.virtualenvs/yt-scraper-env
```

## 4. Configure static files

In the Static files section, add:

- URL: `/static/`
- Directory: `/home/yourusername/Youtube scraping tool/static/`

## 5. Edit the WSGI file

Open the WSGI configuration file from the Web tab and replace its Flask section with the contents of `pythonanywhere_wsgi.py`.

Update this line first:

```python
project_home = "/home/yourusername/Youtube scraping tool"
```

Also replace the secret key value with your own random string.

## 6. Optional environment variables

If you want a custom secret key, add it in the WSGI file:

```python
os.environ.setdefault("FLASK_SECRET_KEY", "your-random-secret")
```

If PythonAnywhere support gives you a specific Chromium path, you can also add:

```python
os.environ.setdefault("CHROMIUM_EXECUTABLE_PATH", "/usr/bin/chromium")
```

## 7. Reload the site

Press the `Reload` button in the Web tab.

## 8. Logs if something fails

Check these from the Web tab:

- Error log
- Server log
- Access log

## Notes about this project

- Generated CSV files are stored in `data/results/`
- Downloaded videos are stored in `data/temp_downloads/`
- The app entrypoint for WSGI is `tool:app`
