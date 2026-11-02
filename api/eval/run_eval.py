"""Scores the AI against links tagged by hand. Calls the real OpenAI API, so it costs a little.

Add links to eval/links.csv, then run this from api/ with OPENAI_API_KEY set:

    python -m eval.run_eval

In links.csv, separate tags with semicolons: https://example.com,article,python;testing
"""

import csv
from pathlib import Path

from app.ai import AIError, analyze, normalize_tags
from app.tasks import BlockedError, FetchError, extract, fetch_html

LINKS_FILE = Path(__file__).parent / "links.csv"


def main() -> None:
    with open(LINKS_FILE, newline="") as file:
        links = list(csv.DictReader(file))

    if not links:
        print(f"No links yet. Add some to {LINKS_FILE}")
        return

    scored = 0
    types_correct = 0
    tags_expected = 0
    tags_found = 0

    for link in links:
        url = link["url"]
        expected_tags = normalize_tags(link["tags"].split(";"))

        try:
            try:
                title, text = extract(fetch_html(url))
            except BlockedError:
                title, text = None, None  # Same as the worker: use the link alone.
            analysis = analyze(url, title, text, [])
        except (FetchError, AIError) as e:
            print(f"SKIPPED {url}: {e}")
            continue

        ai_tags = normalize_tags(analysis.tags)
        matches = set(expected_tags) & set(ai_tags)

        scored += 1
        types_correct += analysis.content_type == link["content_type"]
        tags_expected += len(expected_tags)
        tags_found += len(matches)

        print(f"\n{url}")
        print(f"  type: {analysis.content_type} (expected {link['content_type']})")
        print(f"  tags: {ai_tags} (expected {expected_tags})")
        print(f"  summary: {analysis.summary}")

    print(f"\nScored {scored} of {len(links)} links")
    if scored:
        print(f"Type correct: {types_correct}/{scored}")
    if tags_expected:
        print(f"Your tags the AI also picked: {tags_found}/{tags_expected}")


if __name__ == "__main__":
    main()
