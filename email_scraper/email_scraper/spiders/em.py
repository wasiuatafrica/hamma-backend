import re
from scrapy import Spider, Request

class EmailSpider(Spider):
    name = 'email_spider'
    
    # Define the start URLs for the Scrapy spider
    def start_requests(self):
        # Generate URLs for the pages you want to scrape
        for page_num in range(1, 7728):
            url = f"https://www.nairaland.com/1131485/nigerian-stock-exchange-market-pick/{page_num}"
            yield Request(url, callback=self.parse, errback=self.handle_error)
    
    # Define a callback to process the response
    def parse(self, response):
        # Extract emails using regex
        emails = re.findall(r'[\w\.-]+@[\w\.-]+', response.text)
        
        # Yield each email as an item
        for email in set(emails):
            yield {'email': email}
    
    # Handle errors during scraping
    def handle_error(self, failure):
        self.logger.error(f"Failed to scrape {failure.request.url}: {failure}")
