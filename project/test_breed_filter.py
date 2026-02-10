#!/usr/bin/env python3
"""
Quick test script to verify breed filtering is working correctly.
Scrapes and validates AKC breeds, reporting counts and filtering results.
"""

import sys
from breed_akc import get_breed_list

print("=" * 70)
print("Testing AKC Breed Filtering")
print("=" * 70)

breed_list = get_breed_list()

print(f"\n✅ Total breeds found: {len(breed_list)}")

# Check for problematic entries
problematic = []
for norm_name, info in breed_list.items():
    display = info['display_name'].lower()
    url = info['akc_url'].lower()
    
    # List entries that should not be there
    if any(kw in display for kw in ['group', 'breeds', 'dogs', 'hairless', 'hypoallergenic', 'best', 'largest']):
        problematic.append({
            'display': info['display_name'],
            'url': info['akc_url'],
            'reason': 'Contains banned keyword'
        })
    
    # Check for pagination/category URLs (not single-breed pages)
    if '/page/' in url:
        problematic.append({
            'display': info['display_name'],
            'url': info['akc_url'],
            'reason': 'Pagination URL'
        })

if problematic:
    print(f"\n⚠️  Found {len(problematic)} problematic entries:")
    for entry in problematic[:10]:
        print(f"   - {entry['display']} ({entry['reason']})")
        print(f"     URL: {entry['url']}")
    if len(problematic) > 10:
        print(f"   ... and {len(problematic) - 10} more")
else:
    print("\n✅ No problematic entries found!")

# Show some valid examples
print("\n📋 Sample valid breeds:")
breed_names = sorted([info['display_name'] for info in breed_list.values()])
for name in breed_names[:10]:
    print(f"   ✓ {name}")
if len(breed_names) > 10:
    print(f"   ... and {len(breed_names) - 10} more")

print("\n" + "=" * 70)
