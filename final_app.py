import os
import re
import google.generativeai as genai
import mysql.connector
from datetime import datetime, timedelta
import dateparser
from dotenv import load_dotenv
import spacy
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify
from scrape_utils import scrape_news_click

# Flask app initialization
app = Flask(__name__)

load_dotenv()
genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Load spaCy's English NER model
nlp = spacy.load("en_core_web_sm")

# Define generation parameters for Gemini API
generation_config = {
    "temperature": 0.5,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
}

# Initialize the Gemini model
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config
)

# Database connection details
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "abhijay",
    "database": "newsdb"
}

# List of supported news categories
CATEGORIES = ["home", "sports", "technology", "business", "politics", "education"]
LATEST_KEYWORDS = ["latest", "hot", "top", "breaking", "trending"]  # Maps to "home_news"

# Patterns for date removal in keyword extraction
DATE_PATTERNS = [
    r"\b(today|yesterday|tomorrow)\b",
    r"\b(on \d{2}/\d{2}/\d{4})\b",
    r"\b(last|next) (Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b"
]

# Function to connect to the database
def connect_db():
    return mysql.connector.connect(**DB_CONFIG)

# Function to fetch news from the database with trimming spaces for keyword matching
def fetch_news_from_db(category, date, keyword=None):
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)
    table_name = f"{category}_news"
    
    if keyword:
        normalized_keyword = keyword.lower().replace(" ", "")
        query = f"""
            SELECT headline, summary, news_link 
            FROM {table_name} 
            WHERE date_published = %s 
            AND (
                (LOWER(REPLACE(headline, ' ', '')) NOT LIKE 'noheadlineavailable' 
                 AND LOWER(REPLACE(headline, ' ', '')) LIKE %s)
                OR 
                (LOWER(REPLACE(headline, ' ', '')) LIKE 'noheadlineavailable' 
                 AND LOWER(REPLACE(summary, ' ', '')) LIKE %s)
            )
            ORDER BY id DESC LIMIT 10
        """
        cursor.execute(query, (date, f"%{normalized_keyword}%", f"%{normalized_keyword}%"))
    else:
        query = f"""
            SELECT headline, summary, news_link 
            FROM {table_name} 
            WHERE date_published = %s 
            ORDER BY id DESC LIMIT 10
        """
        cursor.execute(query, (date,))
    
    news_list = cursor.fetchall()

    # Fix the links
    for item in news_list:
        link = item['news_link'].strip()
        
        # Remove duplicate domain if present
        if link.startswith("https://www.indiatoday.inhttps://www.indiatoday.in"):
            link = link.replace("https://www.indiatoday.in", "", 1)
        
        # Add domain if missing
        if not link.startswith(("http://", "https://")):
            link = "https://www.indiatoday.in" + link
        
        item['news_link'] = link

    cursor.close()
    conn.close()

    return news_list



def clean_keyword(keyword):
    """Removes unwanted words like 'in ipl yesterday' or 'on 31/03/2025' after the main entity."""
    # First split on "in" and take the first part
    keyword = re.split(r"\bin\b", keyword, maxsplit=1)[0].strip()
    # Then split on "on" and take the first part
    keyword = re.split(r"\bon\b", keyword, maxsplit=1)[0].strip()
    return keyword

def extract_keyword(user_message):
    """Extracts only PERSON and ORG entities. If none, tries regex extraction."""
    # Remove special characters (?, ., !, etc.)
    user_message = re.sub(r"[^\w\s]", "", user_message)

    # Process text using spaCy
    doc = nlp(user_message)

    # Extract PERSON and ORG entities
    entities = [ent.text for ent in doc.ents if ent.label_ in ["PERSON", "ORG"]]

    # If no entity found, try regex to extract after "about"
    if not entities:
        match = re.search(r"about (.+)", user_message, re.IGNORECASE)
        if match:
            keyword = match.group(1).strip()
            
            # Remove date-related words
            for pattern in DATE_PATTERNS:
                keyword = re.sub(pattern, "", keyword, flags=re.IGNORECASE).strip()

            # Remove unwanted words after "in"
            keyword = clean_keyword(keyword)

            return keyword if keyword else None
    return " ".join(entities) if entities else None

def get_weekday_date(reference, target_weekday, direction="last"):
    """Finds the date for the last or next occurrence of a given weekday."""
    days_map = {
        "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, 
        "Friday": 4, "Saturday": 5, "Sunday": 6
    }
    
    if target_weekday not in days_map:
        return None  # Invalid weekday name

    target_day_num = days_map[target_weekday]
    current_day_num = reference.weekday()

    if direction == "last":  # Find last occurrence
        delta_days = (current_day_num - target_day_num) % 7 or 7
        return reference - timedelta(days=delta_days)
    elif direction == "next":  # Find next occurrence
        delta_days = (target_day_num - current_day_num) % 7 or 7
        return reference + timedelta(days=delta_days)
    
    return None

def convert_date(date_str):
    today = datetime.today()

    # Handle relative dates manually
    if date_str.lower() == "yesterday":
        return (today - timedelta(days=1)).strftime('%Y-%m-%d')
    elif date_str.lower() == "tomorrow":
        return (today + timedelta(days=1)).strftime('%Y-%m-%d')

    # Handle "last Monday", "next Friday", etc.
    words = date_str.lower().split()
    if len(words) == 2 and words[0] in ["last", "next"] and words[1].capitalize() in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
        weekday_date = get_weekday_date(today, words[1].capitalize(), direction=words[0])
        return weekday_date.strftime('%Y-%m-%d') if weekday_date else None

    # Use dateparser for regular dates
    parsed_date = dateparser.parse(date_str)
    return parsed_date.strftime('%Y-%m-%d') if parsed_date else None

def extract_date(user_message):
    """Extracts DATE entities using spaCy and converts them if needed."""
    # First check if the message contains a date in dd/mm/yyyy or dd-mm-yyyy format
    date_match = re.search(r'\b(\d{1,2})([/-])(\d{1,2})\2(\d{4})\b', user_message)

    if date_match:
        day, sep, month, year = date_match.groups()
        try:
            # Validate the date
            datetime.strptime(f"{day}{sep}{month}{sep}{year}", f"%d{sep}%m{sep}%Y")

            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        except ValueError:
            pass  # If invalid date, proceed with spaCy processing
    
    # Process text using spaCy
    doc = nlp(user_message)
    
    # Extract DATE entity
    date_entities = [ent.text for ent in doc.ents if ent.label_ == "DATE"]
    
    if date_entities:

        return convert_date(date_entities[0])
    
    return None


# Function to extract category from user input
def extract_category(user_message):
    user_message_lower = user_message.lower()
    if any(keyword in user_message_lower for keyword in LATEST_KEYWORDS):
        return "home"
    for category in CATEGORIES:
        if category in user_message_lower:

            return category
    return "home"

# Function to check if the message is about news
def is_news_query(user_message):
    return "news" in user_message.lower() or any(keyword in user_message.lower() for keyword in LATEST_KEYWORDS)

# Function to generate news-related prompt
def generate_news_prompt(category, date, news_data, keyword=None):
    if news_data:
        news_text = "\n".join(
            [f"🔹 {news['headline']}\n{news['summary']}\n[Read More]({news['news_link']})" for news in news_data]
        )
        
        if keyword:
            title = f"Filtered News on {keyword}"
        else:
            title = f"{category.capitalize()} News"
        
        prompt = f"""
        You are named as JAZZ, a news chatbot.
        **{title} for {date}:**
        {news_text}
        
        Use this information to provide only the specific news from the given information if the user asks for details.
        Also, recommend other relevant news topics they might be interested in.
        Ensure the response is **structured** with clear **headlines**, **summaries**, and clickable "Read More" links**.
        **Want to know more? Click "Read More" for full details!**
        """
    else:
        prompt = """
       You are named as JAZZ, a news chatbot.
        No news found for the requested category and date.
        Ask the user if they want news from other categories like (latest, sports, technology, education, politics, business) or any other particular dates.
        """
    return prompt

# Function to generate prompt for non-news queries
def generate_non_news_prompt():
    return """
    You are named as JAZZ, a news chatbot.
    Ask the user for specific domains like (latest, sports, technology, education, politics, business).
    If it is a casual conversation, respond intelligently.
    """

def scrape_news(url):
    """Scrapes news content from the given URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
    
    soup = BeautifulSoup(response.text, "html.parser")

    # Extracting headlines and content
    h1_tags = [h1.get_text(strip=True) for h1 in soup.find_all("h1")]
    h2_tags = [h2.get_text(strip=True) for h2 in soup.find_all("h2", class_="jsx-ace90f4eca22afc7")]
    p_tags = [p.get_text(strip=True) for p in soup.find_all("p")]

    # Extract image from the specific div
    image_div = soup.find("div", class_="Story_associate__image__bYOH_ topImage")
    img_tag = image_div.find("img") if image_div else None
    img_url = img_tag["src"] if img_tag and img_tag.get("src") else None

    return {
        "headlines": h1_tags ,
        "summary": h2_tags,
        "paragraphs": p_tags,
        "image": img_url
    }
# Store chat sessions
chat_sessions = {}

# Define news categories with URLs
CATEGORIES = {
    "home": "https://www.indiatoday.in/",
    "sports": "https://www.indiatoday.in/sports",
    "technology": "https://www.indiatoday.in/technology",
    "business": "https://www.indiatoday.in/business",
    "politics": "https://www.indiatoday.in/politics",
    "education": "https://www.indiatoday.in/education"
}

# Function to fetch news from India Today
def fetch_news(category):
    url = CATEGORIES.get(category, CATEGORIES["home"])
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})

    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    articles = soup.find_all("article", class_="B1S3_story__card__A_fhi")

    news_list = []

    for article in articles[:15]:  # Get top 15 news articles
        # Extract category
        category_tag = article.find("div", class_="story__cat")
        news_category = category_tag.find("h4").get_text(strip=True) if category_tag else "General"

        # Extract headline
        headline_tag = article.find("h2")
        headline = headline_tag.get_text(strip=True) if headline_tag else "No headline available"

        # Extract summary
        summary_tag = article.find("div", class_="B1S3_story__shortcont__inicf")
        summary = summary_tag.find("p").get_text(strip=True) if summary_tag else "No summary available"

        # Extract news link
        link_tag = article.find("a")
        news_link = link_tag["href"] if link_tag else "#"

        # Extract image
        image_tag = article.find("div", class_="B1S3_story__thumbnail___pFy6")
        image = image_tag.find("img")["src"] if image_tag and image_tag.find("img") else "static/no-image.jpg"

        news_list.append({
            "category": news_category,
            "headline": headline,
            "summary": summary,
            "image": image,
            "link": news_link
        })

    return news_list

# Home route for news
@app.route('/')
def home():
    news = fetch_news("home")
    return render_template('index1.html', news=news, category="Home")

# Category-based news route
@app.route('/<category>')
def category_news(category):
    if category not in CATEGORIES:
        return "Category not found", 404

    news = fetch_news(category)
    return render_template('index1.html', news=news, category=category.capitalize())

@app.route("/news_details")
def news_details():
    url = request.args.get("url")
    if not url:
        return "No article URL provided!", 400

    # Ensure URL starts with "https://www.indiatoday.in"
    if not url.startswith("https://www.indiatoday.in"):
        url = "https://www.indiatoday.in" + url

    news_data = scrape_news(url)
    if not news_data:
        return "Failed to fetch news data!", 500

    return render_template("news_details.html", news=news_data)


# Jazz Bot page route
@app.route("/jazzbot")
def jazzbot():
    return render_template("index.html")  # Loads chatbot page

# Chatbot response route
@app.route("/chat", methods=["POST"])
def chat():
    # Get user message from JSON request
    user_message = request.json.get("message", "").strip()
    session_id = request.remote_addr  # Using IP as session ID
    
    # Initialize chat session if not exists
    if session_id not in chat_sessions:
        chat_sessions[session_id] = {
            "chat": model.start_chat(history=[]),
            "first_message": True
        }
    
    chat_session = chat_sessions[session_id]
    
    # Process message using your chatbot logic
    if is_news_query(user_message):
        date = extract_date(user_message) or datetime.now().strftime("%Y-%m-%d")
        category = extract_category(user_message)
        keyword = extract_keyword(user_message)
        news_data = fetch_news_from_db(category, date, keyword)
        prompt = generate_news_prompt(category, date, news_data, keyword)
    else:
        prompt = generate_non_news_prompt()
    
    # Get response from Gemini
    response = chat_session["chat"].send_message(prompt)
    model_response = response.text.replace("*", "").replace("\n", "<br>")  # HTML line breaks
    
    return jsonify({"response": model_response})
@app.route('/read_more', methods=['POST'])
def read_more():
    data = request.get_json()
    url = data.get("url")
    
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    news_content = scrape_news_click(url)

    if not news_content:
        return jsonify({"error": "Unable to scrape content"}), 500

    # Combine scraped content into a single string
    combined_text = ""
    if news_content.get("headlines"):
        combined_text += "\n".join(news_content["headlines"]) + "\n\n"
    if news_content.get("summary"):
        combined_text += "\n".join(news_content["summary"]) + "\n\n"
    if news_content.get("paragraphs"):
        combined_text += "\n".join(news_content["paragraphs"])
    # Gemini prompt
    prompt = f"""
    <news data>
    {combined_text}

    The output must be in the format **headlines** then **summary** then **paragraph**.
    The paragraph part should be in 3 paragraphs with detailed explanation.
    """

    try:
        response = model.generate_content(prompt)
        summary = response.text
        return jsonify({"summary": summary})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Run Flask app
if __name__ == "__main__":
    app.run(debug=True,port=5000)
