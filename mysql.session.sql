CREATE DATABASE IF NOT EXISTS newsdb;
USE newsdb;

-- Table for Home News
CREATE TABLE IF NOT EXISTS home_news (
    id INT AUTO_INCREMENT PRIMARY KEY,
    headline VARCHAR(500) NOT NULL,
    summary TEXT,
    news_link VARCHAR(1000),
    image VARCHAR(1000),
    date_published DATE NOT NULL
);

-- Table for Sports News
CREATE TABLE IF NOT EXISTS sports_news (
    id INT AUTO_INCREMENT PRIMARY KEY,
    headline VARCHAR(500) NOT NULL,
    summary TEXT,
    news_link VARCHAR(1000),
    image VARCHAR(1000),
    date_published DATE NOT NULL
);

-- Table for Technology News
CREATE TABLE IF NOT EXISTS technology_news (
    id INT AUTO_INCREMENT PRIMARY KEY,
    headline VARCHAR(500) NOT NULL,
    summary TEXT,
    news_link VARCHAR(1000),
    image VARCHAR(1000),
    date_published DATE NOT NULL
);

-- Table for Business News
CREATE TABLE IF NOT EXISTS business_news (
    id INT AUTO_INCREMENT PRIMARY KEY,
    headline VARCHAR(500) NOT NULL,
    summary TEXT,
    news_link VARCHAR(1000),
    image VARCHAR(1000),
    date_published DATE NOT NULL
);

-- Table for Politics News
CREATE TABLE IF NOT EXISTS politics_news (
    id INT AUTO_INCREMENT PRIMARY KEY,
    headline VARCHAR(500) NOT NULL,
    summary TEXT,
    news_link VARCHAR(1000),
    image VARCHAR(1000),
    date_published DATE NOT NULL
);

-- Table for Education News
CREATE TABLE IF NOT EXISTS education_news (
    id INT AUTO_INCREMENT PRIMARY KEY,
    headline VARCHAR(500) NOT NULL,
    summary TEXT,
    news_link VARCHAR(1000),
    image VARCHAR(1000),
    date_published DATE NOT NULL
);
INSERT INTO business_news (
    id,
    headline,
    summary,
    news_link,
    image,
    date_published
  )
VALUES (
    id:int,
    'headline:varchar',
    'summary:text',
    'news_link:varchar',
    'image:varchar',
    'date_published:date'
  );