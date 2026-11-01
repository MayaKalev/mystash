from pathlib import Path

import httpx
import pytest

from app import tasks
from app.models import Item, User

PAGES = Path(__file__).parent / "pages"


def read_page(name):
    return (PAGES / name).read_text()


def fake_site(status=200, body="", content_type="text/html"):
    """A fake network for fetch_html: every request gets this response."""

    def handler(request):
        return httpx.Response(status, text=body, headers={"content-type": content_type})

    return httpx.MockTransport(handler)


def make_item(db, url="https://example.com/post"):
    user = User(email="maya@example.com", password_hash="x")
    db.add(user)
    db.commit()
    item = Item(user_id=user.id, url=url, status="pending")
    db.add(item)
    db.commit()
    return item


# --- extract -----------------------------------------------------------------


def test_extract_article():
    title, text = tasks.extract(read_page("article.html"))
    assert title == "How Python Virtual Environments Work"
    assert "virtual environment is a folder" in text
    # Menus and footers are left out.
    assert "Subscribe to our newsletter" not in text


def test_extract_falls_back_to_description():
    title, text = tasks.extract(read_page("no_text.html"))
    assert title == "Cool Tool"
    assert text == "Cool Tool turns screenshots into searchable notes."


# --- fetch_html --------------------------------------------------------------


def test_fetch_html_returns_page():
    html = tasks.fetch_html("https://example.com", transport=fake_site(body="<p>Hello</p>"))
    assert html == "<p>Hello</p>"


def test_fetch_html_error_status():
    with pytest.raises(tasks.FetchError, match="404"):
        tasks.fetch_html("https://example.com", transport=fake_site(status=404))


def test_fetch_html_not_a_web_page():
    with pytest.raises(tasks.FetchError, match="not a web page"):
        tasks.fetch_html("https://example.com", transport=fake_site(content_type="application/pdf"))


def test_fetch_html_too_large(monkeypatch):
    monkeypatch.setattr(tasks, "MAX_PAGE_BYTES", 10)
    with pytest.raises(tasks.FetchError, match="too large"):
        tasks.fetch_html("https://example.com", transport=fake_site(body="x" * 100))


def test_fetch_html_timeout():
    def handler(request):
        raise httpx.ReadTimeout("timed out")

    with pytest.raises(tasks.FetchError, match="too long"):
        tasks.fetch_html("https://example.com", transport=httpx.MockTransport(handler))


# --- process_item ------------------------------------------------------------


def test_process_item_saves_text(db, monkeypatch):
    monkeypatch.setattr(tasks, "fetch_html", lambda url: read_page("article.html"))
    item = make_item(db)

    tasks.process_item(item.id)

    db.refresh(item)
    assert item.status == "done"
    assert item.title == "How Python Virtual Environments Work"
    assert "virtual environment is a folder" in item.extracted_text
    assert item.processed_at is not None


def test_process_item_retries_then_fails(db, monkeypatch):
    calls = []

    def always_fails(url):
        calls.append(url)
        raise tasks.FetchError("Could not connect to the site")

    monkeypatch.setattr(tasks, "fetch_html", always_fails)
    monkeypatch.setattr(tasks.time, "sleep", lambda seconds: None)  # don't actually wait
    item = make_item(db)

    tasks.process_item(item.id)

    db.refresh(item)
    assert len(calls) == 3
    assert item.status == "failed"
    assert item.error_message == "Could not connect to the site"


def test_process_item_succeeds_on_second_try(db, monkeypatch):
    responses = [tasks.FetchError("Could not connect to the site"), read_page("article.html")]

    def flaky(url):
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(tasks, "fetch_html", flaky)
    monkeypatch.setattr(tasks.time, "sleep", lambda seconds: None)
    item = make_item(db)

    tasks.process_item(item.id)

    db.refresh(item)
    assert item.status == "done"


def test_process_item_unexpected_error_marks_failed(db, monkeypatch):
    def broken(url):
        raise ValueError("bug")

    monkeypatch.setattr(tasks, "fetch_html", broken)
    item = make_item(db)

    tasks.process_item(item.id)

    db.refresh(item)
    assert item.status == "failed"


def test_process_item_missing_item_does_nothing(db):
    tasks.process_item(12345)  # should not raise
