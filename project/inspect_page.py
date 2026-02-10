import requests
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

url = "https://www.akc.org/dog-breeds/golden-retriever/"
resp = requests.get(url, headers=headers, timeout=10)
soup = BeautifulSoup(resp.text, 'html.parser')

# Look for the breed title to understand page structure
h1 = soup.find('h1')
print(f"H1: {h1.get_text(strip=True) if h1 else 'Not found'}\n")

# Find article or section tags
article = soup.find('article')
section = soup.find('section')
print(f"Article found: {article is not None}")
print(f"Section found: {section is not None}")

# Look for common content container classes
for search_class in ['breed-info', 'breed-content', 'content', 'main-content', 'article-content']:
    div = soup.find('div', class_=search_class)
    if div:
        print(f"Found div with class '{search_class}'")

# Let's look at body paragraphs
body = soup.find('body')
if body:
    all_p = body.find_all('p')
    print(f"\nTotal paragraphs in body: {len(all_p)}")
    print("\nFirst 5 paragraphs:")
    for i, p in enumerate(all_p[:5]):
        text = p.get_text(strip=True)
        if text:  # Only print non-empty
            print(f"P{i}: {text[:120]}...")
        if i > 100:  # Safety limit
            break
