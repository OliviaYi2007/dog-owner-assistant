#!/usr/bin/env python3
"""
Quick test of the breed scraper to validate it collects all breeds and no categories.
"""

from breed_akc import get_breed_list, get_breed_display_names

print("\n🧪 Testing AKC breed scraper...\n")

# Get breed list (will scrape if not cached)
breed_list = get_breed_list()

print(f"\n{'='*60}")
print(f"VALIDATION RESULTS:")
print(f"{'='*60}")
print(f"✓ Total breeds collected: {len(breed_list)}")

# Get display names for dropdown
display_names = get_breed_display_names()
print(f"✓ Display names available: {len(display_names)}")

# Check for forbidden keywords in breed names
forbidden = {'group', 'category', 'collection', 'hypoallergenic', 'hairless', 'large', 'small', 'best'}
contaminated = []
for name in display_names:
    name_lower = name.lower()
    for word in forbidden:
        if word in name_lower:
            contaminated.append((name, word))

if contaminated:
    print(f"\n⚠️  WARNING: Found {len(contaminated)} potentially problematic names:")
    for name, word in contaminated[:10]:  # Show first 10
        print(f"   - {name} (contains '{word}')")
else:
    print(f"✓ No forbidden keywords found in breed names")

# Show some samples
print(f"\n📋 Sample of breeds (first 15):")
for name in sorted(display_names)[:15]:
    print(f"   • {name}")

print(f"\n{'='*60}")
print(f"✅ Scraper test complete!")
print(f"{'='*60}\n")
