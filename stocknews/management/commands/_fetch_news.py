from unittest import result
from stocknews.models import Stock
from django.core.management.base import BaseCommand
from duckduckgo_search import DDGS
from supportwithemail.task import start_conversation


class Command(BaseCommand):
    help = "Disable all PeriodicTask objects not updated in the current month and year"

    def handle(self, *args, **kwargs):
        results = self.fetch_news("hello")
        propmt = f"ensure this news are unique and not duplicate `{results}`"
        ai_resp = start_conversation(
            assistant_id="asst_zOV3oxwThdI76nnsG9BKmcaF", new_message=propmt
        )
        print(ai_resp, "this is the ai resp....")

        # Provide feedback to the user
        self.stdout.write(
            self.style.SUCCESS(f"Successfully disabled  old periodic tasks.")
        )

    def fetch_news(self, stock):
        search_query = f"Nigerian stock market fcmb bank stocks"
        max_results = 5  # @wasiu i did this so to get the max news the sdk can return

        print(f"Searching for news about: {search_query}")
        news_results = self.search_news(search_query, max_results)

        print(f"\nTop {max_results} news results:")
        results = []
        for i, result in enumerate(news_results, 1):
            results.append(result)
            # print("\n", result)
        print(len(results), "this is the result..")
        return results

    def search_news(self, query, max_results=5):
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))
        return results
