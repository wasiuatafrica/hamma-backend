import asyncio
from django.core.management.base import BaseCommand
from duckduckgo_search import DDGS
from stocknews.models import Stock, StockNews
from supportwithemail.task import start_conversation
from django.utils import timezone
from django.db import transaction
from asgiref.sync import sync_to_async
from datetime import datetime


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

        for stock in stocks:
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
                StockNews.objects.filter(title__icontains=result["title"].lower())
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
        unique_news = []
        existing_news = await sync_to_async(list)(
            StockNews.objects.filter(stock=stock).order_by("-published_date")[:10]
        )

        for new_article in news_results:
            is_unique = await self.check_uniqueness_with_ai(new_article, existing_news)
            if is_unique:
                unique_news.append(new_article)
                existing_news.append(
                    StockNews(title=new_article["title"], body=new_article["body"])
                )

        return unique_news

    async def check_uniqueness_with_ai(self, new_article, existing_articles):
        prompt = f"""
        New article:
        Title: {new_article['title']}
        Snippet: {new_article['body'][:200]}...

        Existing articles:
        {self.format_existing_articles(existing_articles)}

        Task: Determine if the new article is substantially different from all existing articles.
        Consider the following:
        1. Is the core news story different?
        2. Does it provide significant new information not present in existing articles?
        3. Is it from a notably different perspective or does it offer unique insights?

        Respond with UNIQUE if the article is substantially different, or NOT_UNIQUE if it's too similar to an existing article.
        Explanation: [Your reasoning here]
        """

        ai_response = await sync_to_async(start_conversation)(
            assistant_id="asst_zOV3oxwThdI76nnsG9BKmcaF", new_message=prompt
        )

        if isinstance(ai_response, dict) and "message" in ai_response:
            response_text = ai_response["message"]
        else:
            self.stdout.write(
                self.style.WARNING(f"Unexpected AI response format: {ai_response}")
            )
            return False

        return "UNIQUE" in response_text.upper()

    def format_existing_articles(self, articles):
        return "\n\n".join(
            [
                f"Title: {article.title}\nSnippet: {article.body[:100]}..."
                for article in articles
            ]
        )
