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


class Command(BaseCommand):
    help = "Fetch unique news articles for stocks and save them to the database"

    # def add_arguments(self, parser):
    # parser.add_argument(
    #     "--max_results",
    #     type=int,
    #     default=5,
    #     help="Maximum number of news results to fetch per stock",
    # )

    def handle(self, *args, **options):
        asyncio.run(self.async_handle(*args, **options))

    async def async_handle(self, *args, **options):
        # max_results = options["max_results"]
        max_results = 3
        stocks = await sync_to_async(list)(Stock.objects.filter(active=True))

        for stock in stocks[25:30]:
            await self.fetch_and_save_news(stock, max_results)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully fetched and saved unique news for {len(stocks)} stocks."
            )
        )

    async def fetch_and_save_news(self, stock, max_results):
        search_query = f"{stock.company} Nigeria"
        news_results = await sync_to_async(self.search_news)(search_query, max_results)
        unique_new_result = []

        # prevent already existing new from going to the ai
        for result in news_results:
            stock_news_exists = await sync_to_async(list)(
                StockNews.objects.filter(
                    stock=stock, title__icontains=result["title"].lower()
                )
            )
            if stock_news_exists:
                print(f"skippinng '{result['title']}' due to diplicate")
                continue
            unique_new_result.append(result)

        unique_news = (
            await self.ensure_uniqueness_with_ai(unique_new_result, stock)
            if len(unique_new_result) > 0
            else []
        )  # prevent sending empty data set to the AI if manual duplicate check already does work and no unique news.

        # async with transaction.atomic():
        print(unique_news)
        for news in unique_news:

            published_date = datetime.strptime(news["date"], "%Y-%m-%dT%H:%M:%S%z")
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
        # unique_news = []
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

        # for new_article in news_results:
        #     is_unique = await self.check_uniqueness_with_ai(new_article, existing_news)
        #     if is_unique:
        #         unique_news.append(new_article)
        #         existing_news.append(
        #             StockNews(title=new_article["title"], body=new_article["body"])
        #         )

        unique_news = await self.get_unique_news(news_results, existing_news)
        # print(unique_news)
        message = json.loads(unique_news["message"])
        print(message)
        return message

    async def get_unique_news(self, news_results, existing_news):
        prompt = f"""
        New articles:{news_results}
        
        Existing articles:{existing_news}

        these are the new articles and the existing articles.
        filter out the articles that are already in the existing articles.
        return only the json unique articles.
        """

        ai_response = await sync_to_async(start_conversation)(
            assistant_id="asst_QZXaDmUdDch9zPQQXWC9fCRG", new_message=prompt
        )

        return ai_response

    def format_existing_articles(self, articles):
        return "\n\n".join(
            [
                f"Title: {article.title}\nSnippet: {article.body[:100]}..."
                for article in articles
            ]
        )
