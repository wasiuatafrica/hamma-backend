# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter


class EmailScraperPipeline:
    def process_item(self, item, spider):
        return item

class EmailPipeline:
    # Open the file when the spider starts
    def open_spider(self, spider):
        self.file = open("emails.txt", "w", encoding="utf-8")
    
    # Process each item (email) and write it to the file
    def process_item(self, item, spider):
        self.file.write(item['email'] + "\n")
        return item
    
    # Close the file when the spider stops
    def close_spider(self, spider):
        self.file.close()
