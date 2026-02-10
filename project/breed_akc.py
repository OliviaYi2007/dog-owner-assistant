import json
import os
import re
import time
from typing import Dict, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Cache paths
BREED_LIST_CACHE = "breed_list_cache.json"
BREED_CONTENT_CACHE_DIR = "breed_content_cache"

# AKC URLs
AKC_BREED_INDEX_BASE = "https://www.akc.org/dog-breeds/"
AKC_BASE_URL = "https://www.akc.org"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

EXCLUDED_SLUGS = {
    "page", "sporting", "hound", "working", "terrier", "toy", "non-sporting", "herding",
    "group", "groups", "mix", "mixed", "all", "breeds", "hypoallergenic", "hairless",
    "large", "small", "best", "types", "categories", "lists", "filter", "search",
}


def _is_valid_breed_url(href: str) -> bool:
    if not href or "/dog-breeds/" not in href:
        return False

    parsed = urlparse(href)
    path = parsed.path.rstrip("/")

    if not re.match(r"^/dog-breeds/[^/]+$", path):
        return False

    parts = path.split("/")
    if len(parts) != 3 or parts[1] != "dog-breeds":
        return False

    slug = parts[2].lower().strip("-")

    if (
        slug in EXCLUDED_SLUGS
        or slug.isdigit()
        or slug.startswith("page")
        or not re.match(r"^[a-z0-9\-]+$", slug)
        or len(slug) < 3
    ):
        return False

    return True


def normalize_breed_name(name: str) -> str:
    name = re.sub(r"[^\w\s\-]", "", name.lower())
    name = re.sub(r"[\s\-]+", "_", name)
    return name.strip("_")


def _fetch_page_with_retries(url: str, max_retries: int = 2) -> Optional[str]:
    headers = {"User-Agent": USER_AGENT}

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, timeout=15, headers=headers)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException:
            if attempt < max_retries - 1:
                time.sleep(1 + attempt * 0.5)
    return None


def _scrape_all_breed_pages() -> Dict[str, Dict[str, str]]:
    breed_map: Dict[str, Dict[str, str]] = {}
    seen_urls: Set[str] = set()

    for page_num in range(1, 26):
        page_url = (
            AKC_BREED_INDEX_BASE
            if page_num == 1
            else f"{AKC_BREED_INDEX_BASE}page/{page_num}/"
        )

        html = _fetch_page_with_retries(page_url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        main = soup.find("main") or soup

        containers = main.find_all(
            ["div", "li", "article"],
            class_=re.compile(r"(breed|card|item|post)", re.I),
        )

        links = []

        if containers:
            for container in containers:
                a = container.find("a", href=True)
                if a and _is_valid_breed_url(a["href"]):
                    links.append(a)
        else:
            for a in main.find_all("a", href=True):
                if _is_valid_breed_url(a["href"]):
                    links.append(a)

        for link in links:
            href = link["href"]
            full_url = urljoin(AKC_BASE_URL, href)

            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            display_name = link.get_text(strip=True)
            if not display_name:
                slug = urlparse(href).path.split("/")[-1]
                display_name = slug.replace("-", " ").title()

            normalized = normalize_breed_name(display_name)
            if normalized and normalized not in breed_map:
                breed_map[normalized] = {
                    "display_name": display_name,
                    "akc_url": full_url,
                }

        if page_num < 25:
            time.sleep(0.3)

    return breed_map


def get_breed_list() -> Dict[str, Dict[str, str]]:
    if os.path.exists(BREED_LIST_CACHE):
        try:
            with open(BREED_LIST_CACHE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    breed_map = _scrape_all_breed_pages()

    if breed_map:
        with open(BREED_LIST_CACHE, "w", encoding="utf-8") as f:
            json.dump(breed_map, f, indent=2, ensure_ascii=False)

    return breed_map


def get_breed_full_profile(breed_name: str) -> Optional[Dict]:
    breed_list = get_breed_list()
    if breed_name not in breed_list:
        return None

    breed_info = breed_list[breed_name]
    os.makedirs(BREED_CONTENT_CACHE_DIR, exist_ok=True)

    cache_file = os.path.join(
        BREED_CONTENT_CACHE_DIR, f"{breed_name}_profile.json"
    )

    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    headers = {"User-Agent": USER_AGENT}

    try:
        resp = requests.get(breed_info["akc_url"], timeout=30, headers=headers)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else breed_info["display_name"]

        body = soup.find("body")
        content = ""

        if body:
            for div in body.find_all("div", recursive=True):
                text = div.get_text(strip=True)
                if (
                    breed_info["display_name"].lower() in text.lower()
                    and 150 < len(text) < 1000
                    and "founded in 1884" not in text.lower()
                ):
                    content = text
                    break

        content = re.sub(r"\s+", " ", content).strip()

        profile = {
            "breed_name": breed_info["display_name"],
            "url": breed_info["akc_url"],
            "title": title,
            "content": content,
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)

        return profile

    except Exception:
        return None


def get_breed_content(breed_name: str) -> Optional[str]:
    profile = get_breed_full_profile(breed_name)
    return profile["content"] if profile else None


def get_breed_display_names() -> list:
    return sorted(
        info["display_name"] for info in get_breed_list().values()
    )


def get_normalized_name_from_display(display_name: str) -> Optional[str]:
    for norm, info in get_breed_list().items():
        if info["display_name"] == display_name:
            return norm
    return None
