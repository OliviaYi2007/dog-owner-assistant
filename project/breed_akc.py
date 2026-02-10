"""
AKC Breed Data Module

This module handles:
1. Scraping ALL AKC breed pages (pages 1-25) with pagination
2. Strict URL validation to exclude categories, groups, and filters
3. Tight HTML selectors to avoid grabbing nav/sidebar/footer links
4. Caching breed list mapping (normalized_name -> {display_name, akc_url})
5. Fetching breed-specific content on demand
6. Caching breed content locally to avoid re-scraping

All caching is done locally in JSON files to avoid aggressive scraping.
"""

import json
import os
import re
import time
from typing import Dict, Optional, Set
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

# Cache file paths
BREED_LIST_CACHE = "breed_list_cache.json"
BREED_CONTENT_CACHE_DIR = "breed_content_cache"

# AKC URLs
AKC_BREED_INDEX_BASE = "https://www.akc.org/dog-breeds/"
AKC_BASE_URL = "https://www.akc.org"

# User-Agent header (realistic browser)
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Slugs to explicitly exclude (known categories, groups, collections)
EXCLUDED_SLUGS = {
    'page', 'sporting', 'hound', 'working', 'terrier', 'toy', 'non-sporting', 'herding',
    'group', 'groups', 'mix', 'mixed', 'all', 'breeds', 'hypoallergenic', 'hairless',
    'large', 'small', 'best', 'types', 'categories', 'lists', 'filter', 'search'
}


def _is_valid_breed_url(href: str) -> bool:
    """
    Strict URL validation: ensure href is ONLY /dog-breeds/<single-slug>/ pattern.
    
    Rejects:
    - /dog-breeds/page/2/ (pagination)
    - /dog-breeds/groups/... (categories)
    - /dog-breeds/hypoallergenic/... (collections)
    - /dog-breeds/sporting/... (group pages)
    - Any multi-segment paths after the breed slug
    
    Accepts:
    - /dog-breeds/golden-retriever/
    - /dog-breeds/shiba-inu/
    """
    if not href or '/dog-breeds/' not in href:
        return False
    
    # Extract path and normalize
    parsed = urlparse(href)
    path = parsed.path.rstrip('/')
    
    # Must match exactly: /dog-breeds/<slug> with no trailing segments
    # Regex: ^/dog-breeds/[^/]+$ ensures single segment between /dog-breeds/ and end
    if not re.match(r'^/dog-breeds/[^/]+$', path):
        return False
    
    # Extract the slug itself
    parts = path.split('/')
    if len(parts) != 3 or parts[0] != '' or parts[1] != 'dog-breeds':
        return False
    
    slug = parts[2].lower().strip('-')
    
    # Reject explicitly excluded slugs
    if slug in EXCLUDED_SLUGS:
        return False
    
    # Reject numeric slugs (pagination) or 'page' variations
    if slug.isdigit() or slug.startswith('page'):
        return False
    
    # Slug must contain only letters, hyphens, numbers (typical dog breed names)
    if not re.match(r'^[a-z0-9\-]+$', slug):
        return False
    
    # Must be at least 3 chars long
    if len(slug) < 3:
        return False
    
    return True


def normalize_breed_name(name: str) -> str:
    """
    Normalize breed name for use as a dict key.
    Converts to lowercase, removes special characters, collapses whitespace.
    """
    # Remove non-alphanumeric (except spaces and hyphens)
    normalized = re.sub(r'[^\w\s\-]', '', name.lower())
    # Collapse spaces/hyphens to single underscore
    normalized = re.sub(r'[\s\-]+', '_', normalized)
    return normalized.strip('_')


def _fetch_page_with_retries(url: str, max_retries: int = 2) -> Optional[str]:
    """Fetch a page with retries and proper headers."""
    headers = {'User-Agent': USER_AGENT}
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, timeout=15, headers=headers)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                wait = 1 + (attempt * 0.5)
                print(f"  ⚠️ Fetch failed, retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"  ❌ Failed after {max_retries} retries: {e}")
                return None
    return None


def _scrape_all_breed_pages() -> Dict[str, Dict[str, str]]:
    """
    Crawl AKC breed pages 1-25, extract breed links using tight selectors,
    apply strict URL validation, and deduplicate.
    
    Returns:
        Dict mapping normalized_name -> {display_name, akc_url}
    """
    breed_map = {}
    seen_urls: Set[str] = set()  # Track URLs to deduplicate
    pages_crawled = 0
    total_links_found = 0
    links_passed_validation = 0
    
    print(f"📥 Starting multi-page breed scraper (pages 1-25)...")
    
    for page_num in range(1, 26):
        # Page 1 is the base URL, page 2+ use /page/N/
        if page_num == 1:
            page_url = AKC_BREED_INDEX_BASE
        else:
            page_url = f"{AKC_BREED_INDEX_BASE}page/{page_num}/"
        
        print(f"\n📄 Fetching page {page_num}: {page_url}")
        
        html = _fetch_page_with_retries(page_url)
        if not html:
            print(f"  ⚠️ Skipping page {page_num}")
            continue
        
        pages_crawled += 1
        soup = BeautifulSoup(html, 'html.parser')
        
        # Tight selector strategy:
        # Look for the main breed list container (avoid nav, header, footer, sidebar)
        # Typically breeds are in <main> or a div with class containing 'breed' or 'card'
        # We'll search within the main content area only
        
        breed_links = []
        
        # Try to find main content area first (avoids nav/header/footer)
        main = soup.find('main')
        search_scope = main if main else soup
        
        # Within main/body, find breed card links
        # AKC usually uses divs with breed/card classes containing <a> tags
        # We'll search for anchors within likely breed containers
        potential_containers = search_scope.find_all(
            ['div', 'li', 'article'],
            class_=re.compile(r'(breed|card|item|post)', re.I)
        )
        
        if potential_containers:
            # If we found specific breed containers, extract links from them
            for container in potential_containers:
                link = container.find('a', href=True)
                if link:
                    href = link.get('href', '').strip()
                    if _is_valid_breed_url(href):
                        breed_links.append((link, href))
        else:
            # Fallback: search for all /dog-breeds/ links in main content
            # but still apply strict URL validation
            all_links = search_scope.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '').strip()
                if _is_valid_breed_url(href):
                    breed_links.append((link, href))
        
        total_links_found += len(breed_links)
        
        # Process extracted links
        for link_elem, href in breed_links:
            # Build full URL
            full_url = urljoin(AKC_BASE_URL, href)
            
            # Skip if we've already seen this URL
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            
            # Extract display name from link text
            display_name = link_elem.get_text(strip=True)
            if not display_name:
                # Fallback to slug if no text
                slug = urlparse(href).path.split('/')[-2]
                display_name = slug.replace('-', ' ').title()
            
            # Normalize for deduplication
            normalized = normalize_breed_name(display_name)
            
            if normalized:
                links_passed_validation += 1
                # If we've seen this normalized name before, keep the "best" display_name
                # (shortest/cleanest one typically)
                if normalized not in breed_map:
                    breed_map[normalized] = {
                        "display_name": display_name,
                        "akc_url": full_url
                    }
                else:
                    # Keep the version with shorter display_name (cleaner)
                    existing = breed_map[normalized]
                    if len(display_name) < len(existing['display_name']):
                        breed_map[normalized] = {
                            "display_name": display_name,
                            "akc_url": full_url
                        }
        
        # Be respectful to the server
        if page_num < 25:
            time.sleep(0.3)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"✅ SCRAPE SUMMARY:")
    print(f"  Pages crawled: {pages_crawled}")
    print(f"  Total links found: {total_links_found}")
    print(f"  Links passed validation: {links_passed_validation}")
    print(f"  Unique breeds (deduplicated): {len(breed_map)}")
    print(f"{'='*60}")
    
    if breed_map:
        # Show sample of 10 breeds
        sample = sorted(list(breed_map.values()), key=lambda x: x['display_name'])[:10]
        print(f"\n📋 Sample of first 10 breeds:")
        for item in sample:
            print(f"  • {item['display_name']}")
    
    return breed_map


def get_breed_list() -> Dict[str, Dict[str, str]]:
    """
    Get the breed list mapping: normalized_name -> {display_name, akc_url}
    
    First checks cache, if not found, scrapes AKC website (all 25 pages) and caches.
    """
    # Check cache first
    if os.path.exists(BREED_LIST_CACHE):
        try:
            with open(BREED_LIST_CACHE, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                print(f"✅ Loaded {len(cached_data)} breeds from cache")
                return cached_data
        except Exception as e:
            print(f"⚠️ Error reading cache: {e}. Will re-scrape.")
    
    # Scrape all pages if cache doesn't exist
    breed_mapping = _scrape_all_breed_pages()
    
    if breed_mapping:
        # Save to cache
        with open(BREED_LIST_CACHE, 'w', encoding='utf-8') as f:
            json.dump(breed_mapping, f, indent=2, ensure_ascii=False)
        print(f"💾 Cached breed list to {BREED_LIST_CACHE}")
    
    return breed_mapping


def get_breed_content(breed_name: str) -> Optional[str]:
    """
    Get the main content text from an AKC breed page.
    
    Args:
        breed_name: Normalized breed name (key from breed list)
    
    Returns:
        Cleaned text content from the breed page, or None if not found
    """
    # Get breed list to find URL
    breed_list = get_breed_list()
    if breed_name not in breed_list:
        return None
    
    breed_info = breed_list[breed_name]
    breed_url = breed_info["akc_url"]
    
    # Check content cache
    os.makedirs(BREED_CONTENT_CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(BREED_CONTENT_CACHE_DIR, f"{breed_name}.json")
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
                print(f"✅ Loaded {breed_info['display_name']} content from cache")
                return cached.get("content")
        except Exception as e:
            print(f"⚠️ Error reading content cache: {e}. Will re-fetch.")
    
    # Fetch breed page content
    headers = {'User-Agent': USER_AGENT}
    print(f"📥 Fetching content for {breed_info['display_name']} from {breed_url}...")
    
    try:
        response = requests.get(breed_url, timeout=30, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "header", "footer"]):
            script.decompose()
        
        # Extract main content - look for common content containers
        content_parts = []
        
        # Try to find main content area
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'content|main|article', re.I))
        
        if main_content:
            # Get all text from main content
            text = main_content.get_text(separator=' ', strip=True)
            content_parts.append(text)
        else:
            # Fallback: get body text
            body = soup.find('body')
            if body:
                text = body.get_text(separator=' ', strip=True)
                content_parts.append(text)
        
        # Clean up the text
        full_content = ' '.join(content_parts)
        # Remove excessive whitespace
        full_content = re.sub(r'\s+', ' ', full_content).strip()
        
        # Cache the content
        cache_data = {
            "breed_name": breed_info["display_name"],
            "url": breed_url,
            "content": full_content
        }
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Cached content for {breed_info['display_name']}")
        
        return full_content
        
    except Exception as e:
        print(f"❌ Error fetching breed content: {e}")
        return None


def get_breed_display_names() -> list:
    """
    Get a sorted list of all breed display names for the dropdown.
    """
    breed_list = get_breed_list()
    display_names = [info["display_name"] for info in breed_list.values()]
    return sorted(display_names)


def get_normalized_name_from_display(display_name: str) -> Optional[str]:
    """
    Convert a display name back to normalized name for lookup.
    """
    breed_list = get_breed_list()
    for normalized, info in breed_list.items():
        if info["display_name"] == display_name:
            return normalized
    return None

