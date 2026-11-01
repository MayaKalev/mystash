"""Background jobs, run by the RQ worker.

process_item takes a saved link, downloads the page, pulls out the main text
and stores it. (Week 3 adds the AI summary and tags.)
"""

import time
from datetime import datetime, timezone

import httpx
import trafilatura

from app.database import SessionLocal
from app.models import Item

MAX_ATTEMPTS = 3
TIMEOUT_SECONDS = 10
MAX_PAGE_BYTES = 5 * 1024 * 1024  # 5 MB
# Only the start of the text is kept. That's plenty for the AI step.
MAX_TEXT_CHARS = 20_000


class FetchError(Exception):
    pass


def fetch_html(url: str, transport: httpx.BaseTransport | None = None) -> str:
    """Download a page and return its HTML. Raises FetchError if that's not possible.

    `transport` is only used by tests, to fake the network.
    """
    client = httpx.Client(
        transport=transport,
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": "MyStash/0.1 (link organizer)"},
    )
    try:
        with client.stream("GET", url) as response:
            response.raise_for_status()

            if "html" not in response.headers.get("content-type", ""):
                raise FetchError("The link is not a web page")

            # Read the page in pieces so a huge file can't fill up memory.
            body = b""
            for chunk in response.iter_bytes():
                body += chunk
                if len(body) > MAX_PAGE_BYTES:
                    raise FetchError("The page is too large")

            return body.decode(response.encoding or "utf-8", errors="replace")
    except httpx.HTTPStatusError as e:
        raise FetchError(f"The site returned an error ({e.response.status_code})") from e
    except httpx.TimeoutException as e:
        raise FetchError("The site took too long to respond") from e
    except httpx.HTTPError as e:
        raise FetchError("Could not connect to the site") from e
    finally:
        client.close()


def extract(html: str) -> tuple[str | None, str | None]:
    """Return (title, text) for a page.

    Uses trafilatura to find the main text. If it finds none, falls back to the
    page's description meta tag.
    """
    metadata = trafilatura.extract_metadata(html)
    title = metadata.title if metadata else None

    text = trafilatura.extract(html)
    if not text and metadata:
        text = metadata.description

    if text:
        text = text[:MAX_TEXT_CHARS]
    return title, text


def process_item(item_id: int) -> None:
    db = SessionLocal()
    try:
        item = db.get(Item, item_id)
        if item is None:
            return  # The item was deleted before the worker got to it.

        item.status = "processing"
        db.commit()

        try:
            fetch_and_extract(item)
        except Exception:
            # A bug or something we didn't expect. Don't leave the item stuck in "processing".
            item.status = "failed"
            item.error_message = "Something went wrong while processing the link"

        item.processed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def fetch_and_extract(item: Item) -> None:
    """Fill in the item's title and text, and set its status to done or failed."""
    # Try a few times, because sites sometimes fail for a moment.
    html = None
    error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            html = fetch_html(item.url)
            break
        except FetchError as e:
            error = str(e)
            if attempt < MAX_ATTEMPTS:
                time.sleep(2 * attempt)

    if html is None:
        item.status = "failed"
        item.error_message = error
        return

    title, text = extract(html)
    if title is None and text is None:
        item.status = "failed"
        item.error_message = "Could not find any text on the page"
        return

    item.title = title
    item.extracted_text = text
    item.status = "done"
    item.error_message = None
