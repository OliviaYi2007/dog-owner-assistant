"""
AKC Breed Data Module

This module handles:
1. Scraping the AKC breed index page to get all breeds
2. Caching breed list mapping (normalized_name -> {display_name, akc_url})
3. Fetching breed-specific content on demand
4. Caching breed content locally to avoid re-scraping

All caching is done locally in JSON files to avoid aggressive scraping.
"""

import json
import os
import re
from typing import Dict, Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

# Cache file paths
BREED_LIST_CACHE = "breed_list_cache.json"
BREED_CONTENT_CACHE_DIR = "breed_content_cache"

# AKC URLs
AKC_BREED_INDEX_URL = "https://www.akc.org/dog-breeds/"
AKC_BASE_URL = "https://www.akc.org"


def normalize_breed_name(name: str) -> str:
    """
    Normalize breed name for use as a key.
    Converts to lowercase and removes special characters.
    """
    # Convert to lowercase and replace spaces/hyphens with underscores
    normalized = re.sub(r'[^\w\s-]', '', name.lower())
    normalized = re.sub(r'[\s-]+', '_', normalized)
    return normalized.strip('_')


def get_breed_list() -> Dict[str, Dict[str, str]]:
    """
    Get the breed list mapping: normalized_name -> {display_name, akc_url}
    
    First checks cache, if not found, scrapes AKC website and caches the result.
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
    
    # Scrape if cache doesn't exist
    print(f"📥 Scraping breed list from {AKC_BREED_INDEX_URL}...")
    breed_mapping = {}
    
    try:
        response = requests.get(AKC_BREED_INDEX_URL, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all breed links - AKC typically has breed links in various containers
        # Look for links that contain '/dog-breeds/' in the href
        breed_links = soup.find_all('a', href=True)
        
        for link in breed_links:
            href = link.get('href', '')
            # Check if this is a breed page link
            if '/dog-breeds/' in href and href != AKC_BREED_INDEX_URL:
                # Get full URL
                full_url = urljoin(AKC_BASE_URL, href)
                
                # Skip the index page itself
                if full_url == AKC_BREED_INDEX_URL:
                    continue
                
                # Extract breed name from link text or URL
                display_name = link.get_text(strip=True)
                if not display_name:
                    # Try to extract from URL
                    path_parts = href.strip('/').split('/')
                    if 'dog-breeds' in path_parts:
                        idx = path_parts.index('dog-breeds')
                        if idx + 1 < len(path_parts):
                            display_name = path_parts[idx + 1].replace('-', ' ').title()
                
                if display_name and len(display_name) > 1:
                    normalized = normalize_breed_name(display_name)
                    if normalized and normalized not in breed_mapping:
                        breed_mapping[normalized] = {
                            "display_name": display_name,
                            "akc_url": full_url
                        }
        
        # If we didn't find enough breeds, try alternative parsing
        if len(breed_mapping) < 50:
            # Try finding breed cards or specific containers
            breed_containers = soup.find_all(['div', 'li'], class_=re.compile(r'breed|card', re.I))
            for container in breed_containers:
                link = container.find('a', href=True)
                if link:
                    href = link.get('href', '')
                    if '/dog-breeds/' in href:
                        full_url = urljoin(AKC_BASE_URL, href)
                        display_name = link.get_text(strip=True) or container.get_text(strip=True)
                        if display_name and len(display_name) > 1:
                            normalized = normalize_breed_name(display_name)
                            if normalized and normalized not in breed_mapping:
                                breed_mapping[normalized] = {
                                    "display_name": display_name,
                                    "akc_url": full_url
                                }
        
        print(f"✅ Found {len(breed_mapping)} breeds")
        
        # Save to cache
        with open(BREED_LIST_CACHE, 'w', encoding='utf-8') as f:
            json.dump(breed_mapping, f, indent=2, ensure_ascii=False)
        print(f"💾 Cached breed list to {BREED_LIST_CACHE}")
        
        return breed_mapping
        
    except Exception as e:
        print(f"❌ Error scraping breed list: {e}")
        # Return empty dict if scraping fails
        return {}


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
    print(f"📥 Fetching content for {breed_info['display_name']} from {breed_url}...")
    
    try:
        response = requests.get(breed_url, timeout=30)
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

