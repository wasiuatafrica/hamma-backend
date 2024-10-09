import asyncio
from django.core.management.base import BaseCommand
from duckduckgo_search import DDGS
from stocknews.models import Stock, StockNews
from supportwithemail.task import start_conversation
from django.utils import timezone
from django.db import transaction
from asgiref.sync import sync_to_async
from datetime import datetime
import json
import time
import json
import ast
import re
from execution.symbol_pair import pairs


def process_company_name(company_name, symbol, sector=None):
    # processed_name = re.sub(
    #     r"\b(Plc|Limited|Ltd|Incorporated|Corp|Company|)\b",
    #     "",
    #     company_name,
    #     flags=re.IGNORECASE,
    # ).strip()

    processed_name = company_name.replace(".", "")

    context_keywords = [symbol.lower(), "Nigeria"]
    # if sector:
    #     context_keywords.append(sector)

    search_query = f"{processed_name} {' '.join(context_keywords)}"

    search_query = re.sub(r"\s+", " ", search_query).strip()

    return search_query


def extract_and_parse_list(input_dict):
    """
    Extracts a message from the input dictionary, removes code block markers
    (either '```python' or '```json'), and parses the content as a list of dictionaries.

    Parameters:
    - input_dict: dict containing the 'message' key with code block markers.

    Returns:
    - List of dictionaries if parsing is successful, else None.
    """

    # Extract the message content
    message_content = input_dict.get("message", "")

    # Remove both Python and JSON code block markers
    clean_content = (
        message_content.replace("```python\n", "")
        .replace("```json\n", "")
        .replace("\n```", "")
    )

    try:
        # Safely evaluate the string as a Python expression using ast.literal_eval
        parsed_list = ast.literal_eval(clean_content)

        # Return the parsed list if it is successfully evaluated as a list
        if isinstance(parsed_list, list):
            return parsed_list
        else:
            print("Parsed content is not a list.")
            return None
    except (SyntaxError, ValueError) as e:
        print(f"Error while parsing: {e}")
        return None


date_formats = [
    "%Y-%m-%dT%H:%M:%S%z",  # ISO format with timezone
    "%Y-%m-%d %H:%M:%S",  # Datetime without timezone
    "%Y-%m-%d",  # Date only
]


class Command(BaseCommand):
    help = "Fetch unique news articles for stocks and save them to the database in batches of 10"

    def handle(self, *args, **options):
        asyncio.run(self.async_handle(*args, **options))

    async def async_handle(self, *args, **options):
        max_results = 6
        stocks = await sync_to_async(list)(
            Stock.objects.filter(active=True).order_by("symbol")[7:]
        )

        batch_size = 10
        total_stocks = len(stocks)

        for i in range(0, total_stocks, batch_size):
            batch = stocks[i : i + batch_size]
            await self.process_batch(batch, max_results)

            if i + batch_size < total_stocks:
                print(f"Sleeping for 1 minute before processing the next batch...")
                await asyncio.sleep(60)  # Sleep for 1 minute between batches

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully fetched and saved unique news for {total_stocks} stocks."
            )
        )

    async def process_batch(self, batch, max_results):
        for stock in batch:
            await self.fetch_and_save_news(stock, max_results)

    async def fetch_and_save_news(self, stock, max_results):
        # search_query = f"{stock.company} Nigeria"
        search_query = process_company_name(
            stock.company.title(), stock.symbol, stock.sector
        )
        print(search_query)
        news_results = await sync_to_async(self.search_news)(search_query, max_results)
        unique_new_result = []

        for result in news_results:
            stock_news_exists = await sync_to_async(list)(
                StockNews.objects.filter(
                    stock=stock, title__icontains=result["title"].lower()
                )
            )
            if stock_news_exists:
                print(f"Skipping '{result['title']}' due to duplicate")
                continue
            unique_new_result.append(result)

        unique_news = (
            await self.ensure_uniqueness_with_ai(unique_new_result, stock)
            if len(unique_new_result) > 0
            else []
        )
        # print(unique_news)
        for news in unique_news:
            # published_date = datetime.strptime(news["date"], "%Y-%m-%dT%H:%M:%S%z")
            published_date = None

            # Attempt to parse the date using different formats
            for date_format in date_formats:
                try:
                    published_date = datetime.strptime(news["date"], date_format)
                    break  # Exit the loop once the date is successfully parsed
                except ValueError:
                    continue  # Try the next format if the current one fails

            if published_date is None:
                print(
                    f"Error: Failed to parse date for news '{news['title']}' with date: {news['date']}"
                )
                continue

            await sync_to_async(StockNews.objects.create)(
                stock=stock,
                title=news["title"],
                body=news["body"],
                url=news["url"],
                published_date=published_date,
            )

        self.stdout.write(
            f"Saved {len(unique_news)} unique news articles for {stock.symbol}"
        )

    def search_news(self, query, max_results=5):
        with DDGS() as ddgs:
            results = list(
                ddgs.news(keywords=query, timelimit="w", max_results=max_results)
            )
            print(results)
        return results

    async def ensure_uniqueness_with_ai(self, news_results, stock):
        now = datetime.now()
        created_ = now - timezone.timedelta(days=7)

        existing_news_query = await sync_to_async(list)(
            StockNews.objects.filter(stock=stock, created__gte=created_)
        )
        existing_news = [
            {
                "date": news.published_date,
                "title": news.title,
                "body": news.body,
                "url": news.url,
            }
            for news in existing_news_query
        ]

        unique_news = await self.get_unique_news(stock, news_results, existing_news)
        print(unique_news)

        parsed_list = extract_and_parse_list(unique_news)

        # if isinstance(unique_news["message"], list):
        #     message = unique_news["message"]
        # elif isinstance(unique_news["message"], str):
        #     message = json.loads(unique_news["message"])

        print(parsed_list)
        return parsed_list

    async def get_unique_news(self, stock, news_results, existing_news):
        prompt = f"""
        New objects:{news_results}
        
        Existing news objects:{existing_news}
        
        company details:
        name:{stock.company}
        sector: {stock.sector}

        """

        ai_response = await sync_to_async(start_conversation)(
            assistant_id="asst_QZXaDmUdDch9zPQQXWC9fCRG", new_message=prompt
        )

        return ai_response
