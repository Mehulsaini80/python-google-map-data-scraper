# Google Maps Business Scraper (FREE — No API Key)

Scrapes Google Maps using a real browser via Playwright.
No credit card. No API key. Completely free.

## Setup

    # 1. Create and activate virtualenv
    python -m venv venv
    venv\Scripts\activate        # Windows
    source venv/bin/activate      # Mac/Linux

    # 2. Install Python packages
    pip install -r requirements.txt

    # 3. Install Chromium browser (one-time, ~130MB)
    playwright install chromium

    # 4. Run the app
    python app.py

Open -> http://localhost:5000

## Features
- Search any keyword + city (e.g. "CA office Jaipur")
- Extracts: Name, Rating, Reviews, Phone, Address, Category, Website
- Export to Excel (.xlsx) or PDF
- Beautiful dark-themed UI
- 100% Free — no API key needed

## Notes
- Scraping takes 30-90 seconds depending on result count
- Google may show CAPTCHA occasionally
  -> Set HEADLESS=false in .env to solve it manually
- Results limited to ~40 per search (Google Maps browser limit)
