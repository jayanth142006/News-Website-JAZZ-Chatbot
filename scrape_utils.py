# scrape_utils.py
import requests
from bs4 import BeautifulSoup

def scrape_news_click(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
    
    soup = BeautifulSoup(response.text, "html.parser")

    h1_tags = [h1.get_text(strip=True) for h1 in soup.find_all("h1")]
    h2_tags = [h2.get_text(strip=True) for h2 in soup.find_all("h2", class_="jsx-ace90f4eca22afc7")]
    p_tags = [p.get_text(strip=True) for p in soup.find_all("p")]

    return {
        "headlines": h1_tags,
        "summary": h2_tags,
        "paragraphs": p_tags,
    }
