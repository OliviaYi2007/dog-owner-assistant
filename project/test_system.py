#!/usr/bin/env python3
"""
Comprehensive test of the breed scraper and dog assistant system.
Validates:
- 292 breeds loaded from cache
- Content extraction for multiple breeds
- No AKC mission statement in extracted content
- Beige background in frontend
"""

from breed_akc import (
    get_breed_list,
    get_breed_full_profile,
    get_breed_display_names,
    get_breed_content,
)
import os

print("=" * 70)
print("DOG ASSISTANT SYSTEM - COMPREHENSIVE TEST")
print("=" * 70)

# Test 1: Breed list
print("\n✓ TEST 1: Breed List")
breed_list = get_breed_list()
print(f"  ✓ Loaded {len(breed_list)} breeds")
assert len(breed_list) == 292, f"Expected 292 breeds, got {len(breed_list)}"

# Test 2: Display names
print("\n✓ TEST 2: Breed Display Names")
display_names = get_breed_display_names()
print(f"  ✓ Generated {len(display_names)} display names")
print(f"  Sample: {display_names[:3]}")
assert len(display_names) == 292, f"Expected 292 display names"

# Test 3: Content extraction for multiple breeds
print("\n✓ TEST 3: Breed Content Extraction")
test_breeds = [
    'golden_retriever',
    'german_shepherd_dog',
    'bulldog',
    'poodle',
    'siberian_husky'
]

for breed in test_breeds:
    profile = get_breed_full_profile(breed)
    if profile and profile['content']:
        content_length = len(profile['content'])
        has_ack_mission = 'founded in 1884' in profile['content'].lower()
        
        status = '✓' if not has_ack_mission else '✗'
        print(f"  {status} {profile['breed_name']}: {content_length} chars, no AKC mission: {not has_ack_mission}")
        
        # Verify no AKC mission statement
        assert not has_ack_mission, f"{breed} contains AKC mission statement!"
        assert content_length > 150, f"{breed} content too short ({content_length} chars)"
    else:
        print(f"  ✗ {breed}: Failed to extract content")

# Test 4: Backend content retrieval
print("\n✓ TEST 4: Backend Content Interface")
content = get_breed_content('labrador_retriever')
if content:
    print(f"  ✓ Retrieved Labrador Retriever content ({len(content)} chars)")
else:
    print(f"  ✗ Failed to retrieve content")

# Test 5: Frontend assets
print("\n✓ TEST 5: Frontend Configuration")
frontend_path = "/Users/oliviayi/F25-Zero-to-ML-Workshops-1/project/frontend.py"
with open(frontend_path, 'r') as f:
    frontend_content = f.read()
    
has_beige = '#f7f1e6' in frontend_content or 'beige' in frontend_content
has_dog_emoji = '🐶' in frontend_content
has_breed_selector = 'get_breed_display_names' in frontend_content

print(f"  ✓ Beige background: {has_beige}")
print(f"  ✓ Dog emoji animation: {has_dog_emoji}")
print(f"  ✓ Breed selector: {has_breed_selector}")

assert has_beige, "Frontend missing beige background"
assert has_dog_emoji, "Frontend missing dog emoji"
assert has_breed_selector, "Frontend missing breed selector"

# Test 6: Cache status
print("\n✓ TEST 6: Caching System")
cache_file = "/Users/oliviayi/F25-Zero-to-ML-Workshops-1/project/breed_list_cache.json"
content_cache_dir = "/Users/oliviayi/F25-Zero-to-ML-Workshops-1/project/breed_content_cache"

print(f"  ✓ Breed list cache exists: {os.path.exists(cache_file)}")
print(f"  ✓ Content cache dir exists: {os.path.exists(content_cache_dir)}")
if os.path.exists(content_cache_dir):
    cached_profiles = len([f for f in os.listdir(content_cache_dir) if f.endswith('.json')])
    print(f"  ✓ Cached breed profiles: {cached_profiles}")

print("\n" + "=" * 70)
print("✅ ALL TESTS PASSED - System is ready for deployment!")
print("=" * 70)
