"""Background jobs, run by the RQ worker.

process_item takes a saved link, downloads the page, pulls out the main text,
then asks the AI for a title, summary, type and tags, and stores all of it.
"""

import time
from datetime import datetime, timezone

import httpx
import trafilatura
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import AIError, analyze, normalize_tags
from app.database import SessionLocal
from app.models import Item, ItemTag, Tag

MAX_ATTEMPTS = 3
TIMEOUT_SECONDS = 10
MAX_PAGE_BYTES = 5 * 1024 * 1024  # 5 MB
# Only the start of the text is kept. That's plenty for the AI step.
MAX_TEXT_CHARS = 20_000


class FetchError(Exception):
    pass


class PermanentFetchError(FetchError):
    """A failure that trying again won't fix, such as a 404."""


class BlockedError(PermanentFetchError):
    """The site refused to show us the page, but the link itself may be fine."""


def fetch_html(url: str, transport: httpx.BaseTransport | None = None) -> str:
    """Download a page and return its HTML. Raises FetchError if that's not possible.

    `transport` is only used by tests, to fake the network.
    """
    client = httpx.Client(
        transport=transport,
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
        # Says honestly who we are and how to reach us, as sites ask bots to do.
        headers={
            "User-Agent": "MyStash/0.1 (link organizer; +https://github.com/MayaKalev/mystash)"
        },
    )
    try:
        with client.stream("GET", url) as response:
            response.raise_for_status()

            if "html" not in response.headers.get("content-type", ""):
                raise PermanentFetchError("The link is not a web page")

            # Read the page in pieces so a huge file can't fill up memory.
            body = b""
            for chunk in response.iter_bytes():
                body += chunk
                if len(body) > MAX_PAGE_BYTES:
                    raise PermanentFetchError("The page is too large")

            return body.decode(response.encoding or "utf-8", errors="replace")
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        message = f"The site returned an error ({status})"
        if status in (401, 403):
            raise BlockedError(message) from e
        # 4xx means the request itself is the problem, except "timed out" and "slow down".
        if 400 <= status < 500 and status not in (408, 429):
            raise PermanentFetchError(message) from e
        raise FetchError(message) from e
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
            if item.status != "failed":
                db.commit()  # Keep the text even if the AI step fails.
                analyze_item(db, item)
        except Exception:
            # A bug or something we didn't expect. Don't leave the item stuck in "processing".
            db.rollback()
            item.status = "failed"
            item.error_message = "Something went wrong while processing the link"

        item.processed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def fetch_and_extract(item: Item) -> None:
    """Fill in what we can of the item's title and text, or set its status to failed.

    Blocked or empty pages leave both empty, and the AI then works from the link alone.
    """
    # Try a few times, because sites sometimes fail for a moment.
    html = None
    error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            html = fetch_html(item.url)
            break
        except BlockedError:
            return
        except PermanentFetchError as e:
            error = str(e)
            break
        except FetchError as e:
            error = str(e)
            if attempt < MAX_ATTEMPTS:
                time.sleep(2 * attempt)

    if html is None:
        item.status = "failed"
        item.error_message = error
        return

    item.title, item.extracted_text = extract(html)


def analyze_item(db: Session, item: Item) -> None:
    """Fill in the AI's title, summary, type and tags, and set the status to done or failed."""
    existing_tags = list(db.scalars(select(Tag.name).where(Tag.user_id == item.user_id)))

    try:
        analysis = analyze(item.url, item.title, item.extracted_text, existing_tags)
    except AIError as e:
        item.status = "failed"
        item.error_message = str(e)
        return

    item.title = analysis.title
    item.summary = analysis.summary
    item.content_type = analysis.content_type
    save_ai_tags(db, item, analysis.tags)
    item.status = "done"
    item.error_message = None


def save_ai_tags(db: Session, item: Item, names: list[str]) -> None:
    """Attach tags to the item, reusing the user's existing tags where they match."""
    for name in normalize_tags(names):
        tag = get_or_create_tag(db, item.user_id, name)
        db.add(ItemTag(item_id=item.id, tag_id=tag.id, source="ai"))


def get_or_create_tag(db: Session, user_id: int, name: str) -> Tag:
    """Return the user's tag with this name, creating it if it doesn't exist yet."""
    tag = db.scalar(select(Tag).where(Tag.user_id == user_id, Tag.name == name))
    if tag is None:
        tag = Tag(user_id=user_id, name=name)
        db.add(tag)
        db.flush()  # Gives the new tag its id.
    return tag
