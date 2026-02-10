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
        
        
        breed_links = []
        
        # Try to find main content area first (avoids nav/header/footer)
        main = soup.find('main')
        search_scope = main if main else soup
        
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
                if normalized not in breed_map:
                    breed_map[normalized] = {
                        "display_name": display_name,
                        "akc_url": full_url
                    }
                else:
                    if len(display_name) < len(existing['display_name']):
                        breed_map[normalized] = {
                            "display_name": display_name,
                            "akc_url": full_url
                        }
        
        # Be respectful to the server
        if page_num < 25:
            time.sleep(0.3)
    
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


def get_breed_full_profile(breed_name: str) -> Optional[Dict]:
    """
    Get comprehensive breed-specific information from an AKC breed page.
    Extracts ONLY breed-related content: traits, lifespan, weight, personality, temperament, etc.
    Excludes: navigation, links, images metadata, page structure.
    
    Args:
        breed_name: Normalized breed name (key from breed list)
    
    Returns:
        Dict with: breed_name, url, title, content (breed info only), key_traits
        Returns None if breed not found or fetch fails.
    """
    # Get breed list to find URL
    breed_list = get_breed_list()
    if breed_name not in breed_list:
        return None
    
    breed_info = breed_list[breed_name]
    breed_url = breed_info["akc_url"]
    
    # Check content cache
    os.makedirs(BREED_CONTENT_CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(BREED_CONTENT_CACHE_DIR, f"{breed_name}_profile.json")
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
                print(f"✅ Loaded breed profile for {breed_info['display_name']} from cache")
                return cached
        except Exception as e:
            print(f"⚠️ Error reading content cache: {e}. Will re-fetch.")
    
    # Fetch breed page
    headers = {'User-Agent': USER_AGENT}
    print(f"📥 Fetching breed info for {breed_info['display_name']} from {breed_url}...")
    
    try:
        response = requests.get(breed_url, timeout=30, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title (H1)
        h1 = soup.find('h1')
        page_title = h1.get_text(strip=True) if h1 else breed_info["display_name"]
        
        # Remove non-content elements (nav, footer, ads, scripts, etc.)
        for selector in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript']):
            selector.decompose()
        
        # Find the breed name from the breed info
        breed_display_name = breed_info['display_name']
        
        # Strategy: Find divs that contain the breed name + description
        # These typically contain the breed description text
        body = soup.find('body')
        full_content = ""
        
        if body:
            # Find all divs with substantial text that includes the breed name
            for div in body.find_all('div', recursive=True):
                text = div.get_text(strip=True)
                
                # Check if this div contains the breed name
                if breed_display_name.lower() in text.lower() and len(text) > 150 and len(text) < 1000:
                    # Check if it contains breed-related keywords (not AKC mission statement)
                    lower_text = text.lower()
                    
                    # Skip AKC mission/about text (1000+ chars with "founded in 1884")
                    if 'founded in 1884' in lower_text:
                        continue
                    
                    # Skip navigation text
                    if any(skip in lower_text for skip in ['sign in', 'menu', 'home', 'dog breeds', 'search']):
                        # But only skip if it's MOSTLY nav text
                        nav_count = sum(1 for skip in ['sign in', 'menu', 'home', 'dog breeds', 'search'] if skip in lower_text)
                        if nav_count > 2:
                            continue
                    
                    # This looks like the breed description
                    full_content = text
                    break
        
        # Clean up and normalize whitespace
        full_content = re.sub(r'\s+', ' ', full_content).strip()
        
        # Extract key traits/attributes (look for common patterns)
        traits = {}
        
        # Look for specific dog trait patterns in the content
        trait_keywords = {
            'life span': r'life\s*span[:\s]+([^\.]+)',
            'weight': r'weight[:\s]+([^\.]+)',
            'height': r'height[:\s]+([^\.]+)',
            'size': r'size[:\s]+([^\.]+)',
            'temperament': r'temperament[:\s]+([^\.]+)',
            'personality': r'personality[:\s]+([^\.]+)',
            'energy level': r'energy\s*level[:\s]+([^\.]+)',
            'grooming': r'grooming[:\s]+([^\.]+)',
            'hypoallergenic': r'hypoallergenic[:\s]+([^\.]+)',
            'shedding': r'shedding[:\s]+([^\.]+)',
        }
        
        lower_content = full_content.lower()
        for trait_name, pattern in trait_keywords.items():
            match = re.search(pattern, lower_content, re.IGNORECASE)
            if match:
                traits[trait_name] = match.group(1).strip()
        
        # Build breed profile (focused on breed info only)
        profile = {
            "breed_name": breed_info["display_name"],
            "url": breed_url,
            "title": page_title,
            "content": full_content,  # Full breed description and info
            "key_traits": traits,      # Extracted dog traits
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Cache the profile
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(profile, f, indent=2, ensure_ascii=False)
            print(f"💾 Cached breed profile for {breed_info['display_name']}")
        except Exception as e:
            print(f"⚠️ Warning: Could not cache profile: {e}")
        
        return profile
        
    except Exception as e:
        print(f"❌ Error fetching breed profile: {e}")
        return None


def get_breed_content(breed_name: str) -> Optional[str]:
    """
    Get the main content text from an AKC breed page.
    Returns only the focused breed content (traits, personality, lifespan, weight, etc.).
    
    Args:
        breed_name: Normalized breed name (key from breed list)
    
    Returns:
        Cleaned breed information text, or None if not found
    """
    profile = get_breed_full_profile(breed_name)
    if profile:
        return profile.get("content")
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

