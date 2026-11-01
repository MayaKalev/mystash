from pathlib import Path

import httpx
import pytest

from app import tasks
from app.ai import AIError, Analysis
from app.models import Item, ItemTag, Tag, User

PAGES = Path(__file__).parent / "pages"


@pytest.fixture(autouse=True)
def fake_ai(monkeypatch):
    """Tests never call the real AI. This answer is used unless a test replaces it."""

    def analyze(url, title, text, existing_tags):
        return Analysis(
            title="AI title",
            summary="AI summary",
            content_type="article",
            tags=["Python", "virtual environments"],
        )

    monkeypatch.setattr(tasks, "analyze", analyze)


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
    assert item.title == "AI title"
    assert item.summary == "AI summary"
    assert item.content_type == "article"
    assert "virtual environment is a folder" in item.extracted_text
    assert item.processed_at is not None


def test_process_item_saves_lowercase_ai_tags(db, monkeypatch):
    monkeypatch.setattr(tasks, "fetch_html", lambda url: read_page("article.html"))
    item = make_item(db)

    tasks.process_item(item.id)

    db.refresh(item)
    assert [tag.name for tag in item.tags] == ["python", "virtual environments"]
    assert {row.source for row in db.query(ItemTag).all()} == {"ai"}


def test_process_item_reuses_existing_tag_and_tells_ai_about_it(db, monkeypatch):
    monkeypatch.setattr(tasks, "fetch_html", lambda url: read_page("article.html"))
    item = make_item(db)
    db.add(Tag(user_id=item.user_id, name="python"))
    db.commit()

    seen_tags = []

    def analyze(url, title, text, existing_tags):
        seen_tags.extend(existing_tags)
        return Analysis(title="T", summary="S", content_type="other", tags=["PYTHON"])

    monkeypatch.setattr(tasks, "analyze", analyze)

    tasks.process_item(item.id)

    assert seen_tags == ["python"]
    assert db.query(Tag).count() == 1
    assert db.query(ItemTag).count() == 1


def test_process_item_ai_error_keeps_text(db, monkeypatch):
    def fails(url, title, text, existing_tags):
        raise AIError("The AI service could not process this link")

    monkeypatch.setattr(tasks, "fetch_html", lambda url: read_page("article.html"))
    monkeypatch.setattr(tasks, "analyze", fails)
    item = make_item(db)

    tasks.process_item(item.id)

    db.refresh(item)
    assert item.status == "failed"
    assert item.error_message == "The AI service could not process this link"
    assert item.title == "How Python Virtual Environments Work"
    assert "virtual environment is a folder" in item.extracted_text


def test_process_item_blocked_site_uses_link_only(db, monkeypatch):
    calls = []
    seen = []

    def blocked(url):
        calls.append(url)
        raise tasks.BlockedError("The site returned an error (403)")

    def analyze(url, title, text, existing_tags):
        seen.append((url, title, text))
        return Analysis(title="T", summary="S", content_type="other", tags=["python"])

    monkeypatch.setattr(tasks, "fetch_html", blocked)
    monkeypatch.setattr(tasks, "analyze", analyze)
    item = make_item(db)

    tasks.process_item(item.id)

    db.refresh(item)
    assert len(calls) == 1
    assert seen == [("https://example.com/post", None, None)]
    assert item.status == "done"
    assert item.error_message is None


def test_process_item_page_without_text_uses_link_only(db, monkeypatch):
    monkeypatch.setattr(tasks, "fetch_html", lambda url: "<html></html>")
    item = make_item(db)

    tasks.process_item(item.id)

    db.refresh(item)
    assert item.status == "done"
    assert item.extracted_text is None


@pytest.mark.parametrize("status", [401, 403])
def test_fetch_html_refused_means_blocked(status):
    with pytest.raises(tasks.BlockedError):
        tasks.fetch_html("https://example.com", transport=fake_site(status=status))


def test_fetch_html_says_who_we_are():
    seen = []

    def handler(request):
        seen.append(request.headers["user-agent"])
        return httpx.Response(200, text="<p>Hi</p>", headers={"content-type": "text/html"})

    tasks.fetch_html("https://example.com", transport=httpx.MockTransport(handler))

    assert "github.com/MayaKalev/mystash" in seen[0]


def test_process_item_failed_download_skips_ai(db, monkeypatch):
    def fails(url):
        raise tasks.PermanentFetchError("The site returned an error (404)")

    def should_not_run(url, title, text, existing_tags):
        raise AssertionError("The AI should not be called")

    monkeypatch.setattr(tasks, "fetch_html", fails)
    monkeypatch.setattr(tasks, "analyze", should_not_run)
    item = make_item(db)

    tasks.process_item(item.id)

    db.refresh(item)
    assert item.status == "failed"
    assert item.error_message == "The site returned an error (404)"


def test_process_item_does_not_retry_permanent_errors(db, monkeypatch):
    calls = []

    def not_found(url):
        calls.append(url)
        raise tasks.PermanentFetchError("The site returned an error (404)")

    monkeypatch.setattr(tasks, "fetch_html", not_found)
    item = make_item(db)

    tasks.process_item(item.id)

    assert len(calls) == 1


@pytest.mark.parametrize("status", [404, 410, 403])
def test_fetch_html_client_errors_are_permanent(status):
    with pytest.raises(tasks.PermanentFetchError):
        tasks.fetch_html("https://example.com", transport=fake_site(status=status))


@pytest.mark.parametrize("status", [408, 429, 500, 503])
def test_fetch_html_temporary_errors_can_be_retried(status):
    with pytest.raises(tasks.FetchError) as error:
        tasks.fetch_html("https://example.com", transport=fake_site(status=status))
    assert not isinstance(error.value, tasks.PermanentFetchError)


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
