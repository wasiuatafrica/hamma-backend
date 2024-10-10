import os
import requests
from bs4 import BeautifulSoup
from openai import AsyncOpenAI, OpenAI
import openai
import os
import requests
from bs4 import BeautifulSoup
import newspaper


client = OpenAI(
    api_key="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"
)


def get_news_urls(query, num_articles=5):
    """
    Fetches news article URLs related to the query using Google News RSS feed.
    """
    search_url = (
        f"https://news.google.com/rss/search?q={query}&hl=en-NG&gl=NG&ceid=NG:en"
    )
    response = requests.get(search_url)
    soup = BeautifulSoup(response.content, "xml")

    # Limit the number of articles to fetch
    items = soup.findAll("item")[:num_articles]
    urls = [item.link.text for item in items]
    print(f"Fetched {len(urls)} URLs for query: {query}")
    return urls


def fetch_news_article(url):
    """
    Fetches and parses a news article from the provided URL using newspaper3k.
    """
    try:
        # Create an Article object
        article = newspaper.article(url)

        print(f"Fetched article from: {url}")

        # Extract title and text
        title = article.title
        article_text = article.text

        # Print or return the article's title and content
        print(f"Title: {title}")
        print(f"Article content (first 500 characters): {article_text[:100]}...")

        return {"title": title, "content": article_text}

    except Exception as e:
        print(f"Error fetching the article: {e}")
        return None


def summarize_text(text, max_tokens=250):
    """
    Summarizes the given text using OpenAI's API with an async call.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that summarizes news articles.",
                },
                {
                    "role": "user",
                    "content": f"Please summarize the following text: {text}",
                },
            ],
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content.strip()
        # return response['choices'][0]['message']['content'].strip()

    except Exception as e:
        return f"Error in summarizing text: {e}"


def process_articles(urls):
    """
    Processes a list of news article URLs and summarizes their content.
    """

    for idx, url in enumerate(urls, start=1):

        article = fetch_news_article(url)
        print(article)
        summary = summarize_text(article["content"])
        print(f"Article {idx}: {article['title']}")
        print(f"Source: {url}")
        print(f"Summary: {summary}\n")


query = "GTCO stock October 2024"
urls = ["https://thenationonlineng.net/wema-bank-bags-two-awards-at-edge-awards-2024/"]
process_articles(urls)
