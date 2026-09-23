#!/usr/bin/env python3
"""Read a public Spotify playlist's title and description from page metadata.

Usage: python playlist_description.py https://open.spotify.com/playlist/...
Requires only Python's standard library. No Spotify account or API token.
"""

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.metadata = {}

    def handle_starttag(self, tag, attrs):
        if tag != "meta":
            return
        values = dict(attrs)
        key = values.get("property") or values.get("name")
        if key in {"og:title", "og:description", "og:url"}:
            self.metadata[key] = values.get("content", "")


def playlist_id(value):
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in {"open.spotify.com", "spotify.com"}:
        raise ValueError("Use an https://open.spotify.com/playlist/... URL")
    match = re.fullmatch(r"/(?:intl-[a-z]{2}/)?playlist/([A-Za-z0-9]{22})/?", parsed.path)
    if not match:
        raise ValueError("The URL does not contain a valid Spotify playlist ID")
    return match.group(1)


def scrape_description(url):
    identifier = playlist_id(url)
    canonical = f"https://open.spotify.com/playlist/{identifier}"
    request = Request(canonical, headers={"User-Agent": "Mozilla/5.0 (compatible; PlaylistDescription/1.0)"})
    with urlopen(request, timeout=20) as response:
        if response.geturl().startswith("https://accounts.spotify.com/"):
            raise ValueError("Spotify requires sign-in for this playlist")
        page = response.read(3_000_001)
    if len(page) > 3_000_000:
        raise ValueError("Spotify's page is unexpectedly large")
    parser = MetadataParser()
    parser.feed(page.decode("utf-8", errors="replace"))
    data = parser.metadata
    if data.get("og:url", "").rstrip("/") != canonical:
        raise ValueError("Spotify did not return metadata for the requested playlist")
    if not data.get("og:title") or "og:description" not in data:
        raise ValueError("Spotify did not expose the playlist title and description")
    return {"url": canonical, "name": data["og:title"], "description": data["og:description"]}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("url", help="Public Spotify playlist URL")
    args = cli.parse_args()
    try:
        print(json.dumps(scrape_description(args.url), ensure_ascii=False, indent=2))
    except (ValueError, HTTPError, URLError, TimeoutError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
