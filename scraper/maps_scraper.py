import re
import time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout


class PlaywrightMapsScraper:
    """
    Scrapes Google Maps using a real Chromium browser via Playwright.
    No API key required — completely free.
    """

    def __init__(self, headless: bool = True, max_results: int = 20, timeout: int = 60):
        self.headless    = headless
        self.max_results = max_results
        self.timeout     = timeout * 1000   # playwright uses milliseconds

    # ── Main entry point ────────────────────────────────────────────
    def search(self, query: str) -> list:
        results = []
        url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-US",
            )
            page = ctx.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
                self._dismiss_popups(page)
                self._scroll_results(page)
                listings = self._get_listing_links(page)
                results  = self._scrape_each(page, listings)
            except Exception as e:
                raise RuntimeError(f"Scrape failed: {e}")
            finally:
                browser.close()

        return results

    # ── Dismiss cookie / consent popups ─────────────────────────────
    def _dismiss_popups(self, page):
        selectors = [
            'button[aria-label="Accept all"]',
            'button[aria-label="Reject all"]',
            'form[action*="consent"] button',
        ]
        for sel in selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=3000):
                    btn.click()
                    page.wait_for_timeout(800)
                    break
            except Exception:
                pass

    # ── Scroll the left-panel list to load more results ─────────────
    def _scroll_results(self, page):
        try:
            page.wait_for_selector('div[role="feed"]', timeout=15000)
        except PWTimeout:
            return

        feed = page.locator('div[role="feed"]')
        prev_count = 0

        for _ in range(20):
            count = page.locator('a[href*="/maps/place/"]').count()
            if count >= self.max_results:
                break
            if count == prev_count:
                break   # no new items loaded
            prev_count = count
            feed.evaluate("el => el.scrollBy(0, 1200)")
            page.wait_for_timeout(1400)

    # ── Collect unique place URLs from the sidebar ───────────────────
    def _get_listing_links(self, page) -> list:
        anchors = page.locator('a[href*="/maps/place/"]').all()
        seen, links = set(), []
        for a in anchors:
            href = a.get_attribute("href") or ""
            if href and href not in seen:
                seen.add(href)
                links.append(href)
            if len(links) >= self.max_results:
                break
        return links

    # ── Visit each place page and extract all fields ─────────────────
    def _scrape_each(self, page, links: list) -> list:
        results = []
        for href in links:
            try:
                page.goto(href, wait_until="domcontentloaded", timeout=self.timeout)
                page.wait_for_timeout(1500)
                record = self._extract(page)
                if record.get("name") and record["name"] != "N/A":
                    results.append(record)
            except Exception:
                continue
        return results

    # ── Extract all data fields from a single place page ─────────────
    def _extract(self, page) -> dict:

        def safe_text(selector, attr=None):
            try:
                el = page.locator(selector).first
                if not el.is_visible(timeout=3000):
                    return "N/A"
                if attr:
                    return el.get_attribute(attr) or "N/A"
                return (el.inner_text() or "N/A").strip()
            except Exception:
                return "N/A"

        # Name
        name = safe_text('h1.DUwDvf')
        if name == "N/A":
            name = safe_text('h1[class*="fontHeadlineLarge"]')

        # Rating
        rating = safe_text('div.F7nice span[aria-hidden="true"]')
        if rating == "N/A":
            rating = safe_text('span.ceNzKf')

        # Review count
        reviews = "N/A"
        raw = safe_text('div.F7nice span[aria-label*="review"]', "aria-label")
        if raw != "N/A":
            m = re.search(r"([\d,]+)", raw)
            if m:
                reviews = m.group(1).replace(",", "")

        # Category
        category = safe_text('button[jsaction*="category"]')
        if category == "N/A":
            category = safe_text('span.DkEaL')

        # Address
        address = safe_text('button[data-item-id="address"] div.Io6YTe')
        if address == "N/A":
            address = safe_text('[data-tooltip="Copy address"] .Io6YTe')

        # Phone
        phone = safe_text('button[data-item-id*="phone"] div.Io6YTe')
        if phone == "N/A":
            phone = safe_text('[data-tooltip="Copy phone number"] .Io6YTe')

        # Website
        website = safe_text('a[data-item-id="authority"]', "href")
        if website == "N/A":
            website = safe_text('a[aria-label*="website"]', "href")

        return {
            "name":     name,
            "category": category,
            "rating":   rating,
            "reviews":  reviews,
            "phone":    phone,
            "address":  address,
            "website":  website,
        }
