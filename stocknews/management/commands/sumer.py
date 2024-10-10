import newspaper
from django.core.management.base import BaseCommand
from openai import OpenAI

from execution.symbol_pair import pairs
from stocknews.models import Stock, StockNews

client = OpenAI()


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
    if text:
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
    return None


def process_articles(url):
    """
    Processes a list of news article URLs and summarizes their content.
    """

    article = fetch_news_article(url)
    # print(article)
    summary = summarize_text(article["content"])
    print(summary)

    return summary


class Command(BaseCommand):
    help = "provide ai summary"

    def handle(self, *args, **options):
        news_query = StockNews.objects.all()
        for new in news_query:
            try:
                summary = process_articles(new.url)
                new.ai_summary = summary
                new.save()
            except Exception as e:
                print(e)
                continue
