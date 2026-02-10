import requests
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

url = "https://www.akc.org/dog-breeds/golden-retriever/"
resp = requests.get(url, headers=headers, timeout=10)
soup = BeautifulSoup(resp.text, 'html.parser')

# Look for any text content in divs
body = soup.find('body')
if body:
    # Find all divs with text
    divs_with_text = []
    for div in body.find_all('div', recursive=True):
        text = div.get_text(strip=True)
        if len(text) > 100:  # Only substantial text
            divs_with_text.append((len(text), text[:150]))
    
    divs_with_text.sort(reverse=True)
    print(f"Found {len(divs_with_text)} divs with >100 chars text\n")
    print("Top 10 largest text divs:")
    for i, (length, text) in enumerate(divs_with_text[:10]):
        print(f"{i}. Length {length}: {text}...")
        print()
    
    # Also check for spans
    all_text_elems = body.find_all(['p', 'span', 'div', 'section', 'article'])
    print(f"\nTotal elements with text: {len(all_text_elems)}")
    
    # Look for the breed name to figure out structure
    body_text = body.get_text()
    if 'Golden Retriever' in body_text:
        print("\n✓ Golden Retriever found in page text")
        # Find surrounding context
        idx = body_text.find('Golden Retriever')
        start = max(0, idx - 200)
        end = min(len(body_text), idx + 500)
        print(f"\nContext around breed name:\n{body_text[start:end]}")
