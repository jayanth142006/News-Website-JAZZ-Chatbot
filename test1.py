import re
import google.generativeai as genai
import mysql.connector
from datetime import datetime, timedelta
import os
import dateparser
from dotenv import load_dotenv
import spacy

# Load API key securely from an environment variable
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
        # Remove spaces from the keyword for better matching
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
        query = f"SELECT headline, summary, news_link FROM {table_name} WHERE date_published = %s ORDER BY id DESC LIMIT 10"
        cursor.execute(query, (date,))
    
    news_list = cursor.fetchall()
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
            print(category)
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
        Ensure the response is **structured** with clear **headlines, summaries, and clickable "Read More" links**.
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

# Function to process user input and get response
def chat():
    chat_session = model.start_chat(history=[])
    print("\n🎙️ Welcome to JAZZS News Chatbot! How can I help you with News today.\n")
    while True:
        user_message = input("You: ").strip()
        if user_message.lower() in ["exit", "quit"]:
            print("🔚 Exiting chatbot. Have a great day!")
            break

        if is_news_query(user_message):
            date = extract_date(user_message) or datetime.now().strftime("%Y-%m-%d")
            category = extract_category(user_message)
            keyword = extract_keyword(user_message)
            news_data = fetch_news_from_db(category, date, keyword)
            prompt = generate_news_prompt(category, date, news_data, keyword)
        else:
            prompt = generate_non_news_prompt()
        
        response = chat_session.send_message(prompt)
        model_response = response.text.replace("*", "").replace("\n", "\n")
        print(f"\n🤖: {model_response}\n")

# Run chatbot in terminal
if __name__ == "__main__":
    chat()