import requests
import mysql.connector
import schedule
import time
from bs4 import BeautifulSoup
from datetime import datetime

# Database connection details
DB_HOST = "localhost"       # Change if using a remote MySQL server
DB_USER = "root"            # Use your MySQL username
DB_PASS = "abhijay"         # Enter your MySQL root password
DB_NAME = "newsdb"          # Your database name

# Define news categories with URLs
CATEGORIES = {
    "home": "https://www.indiatoday.in/",
    "sports": "https://www.indiatoday.in/sports",
    "technology": "https://www.indiatoday.in/technology",
    "business": "https://www.indiatoday.in/business",
    "politics": "https://www.indiatoday.in/politics",
    "education": "https://www.indiatoday.in/education"
}

# Function to connect to MySQL with error handling
def connect_db():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME
        )
        return conn
    except mysql.connector.Error as err:
        print(f"❌ Database Connection Error: {err}")
        return None

# Function to check if news already exists in the database based on headline OR summary
def news_exists(cursor, table, headline, summary):
    query = f"SELECT COUNT(*) FROM {table} WHERE headline = %s AND summary=%s"
    cursor.execute(query, (headline, summary))
    return cursor.fetchone()[0] > 0

# Function to insert news into the database
def insert_news(category, news_list):
    conn = connect_db()
    if conn is None:
        return  # Skip if the database connection failed

    cursor = conn.cursor()
    table_name = f"{category}_news"  # Table name format (e.g., sports_news, politics_news)
    
    for news in news_list:
        if not news_exists(cursor, table_name, news["headline"], news["summary"]):  # Check for duplicates
            query = f"""
            INSERT INTO {table_name} (headline, summary, news_link, image, date_published)
            VALUES (%s, %s, %s, %s, %s)
            """
            values = (news["headline"], news["summary"], news["link"], news["image"], news["date"])
            cursor.execute(query, values)
            conn.commit()

    cursor.close()
    conn.close()

# Function to fetch news from India Today
def fetch_news(category):
    url = CATEGORIES.get(category, CATEGORIES["home"])
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})

    if response.status_code != 200:
        print(f"❌ Failed to fetch {category} news!")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    articles = soup.find_all("article", class_="B1S3_story__card__A_fhi")

    news_list = []
    today_date = datetime.now().strftime("%Y-%m-%d")

    for article in articles[:20]:  # Get top 20 news articles
        # Extract headline safely
        headline_tag = article.find("h2")
        headline = headline_tag.get_text(strip=True) if headline_tag else "No headline available"

        # Extract summary safely
        summary_tag = article.find("div", class_="B1S3_story__shortcont__inicf")
        summary = summary_tag.find("p").get_text(strip=True) if summary_tag else "No summary available"

        # Extract news link safely
        link_tag = article.find("a")
        news_link = "https://www.indiatoday.in" + link_tag["href"] if link_tag and "href" in link_tag.attrs else "#"

        # Extract image safely
        image_tag = article.find("div", class_="B1S3_story__thumbnail___pFy6")
        image = image_tag.find("img")["src"] if image_tag and image_tag.find("img") else "static/no-image.jpg"

        # If headline is missing, use summary for duplicate check
        check_text = summary if headline == "No headline available" else headline

        # Ensure at least either a headline or a summary is available
        if check_text != "No summary available":
            news_list.append({
                "date": today_date,
                "headline": headline,
                "summary": summary,
                "image": image,
                "link": news_link
            })
    return news_list

# Function to scrape and store news for all categories
def update_news():
    for category in CATEGORIES.keys():
        print(f"🔍 Fetching {category} news...")
        news = fetch_news(category)
        insert_news(category, news)
    print("✅ News updated in database!")

# Run the scraper every 1 hour
schedule.every(1).hours.do(update_news)

if __name__ == "__main__":
    update_news()  # Run initially
    while True:
        schedule.run_pending()
        time.sleep(60)  # Wait for 1 minute before checking again
