from django.db import models
import auto_prefetch
from portfolio.models import Stock


# Create your models here.
class StockNews(auto_prefetch.Model):

    stock = models.ForeignKey(
        Stock, on_delete=models.CASCADE, related_name="stock_news"
    )
    title = models.CharField(max_length=225)
    body = models.TextField()
    published_date = models.DateField(null=True, blank=True)
    url = models.TextField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.stock.symbol}- {self.title}"
