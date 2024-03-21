from django.contrib import admin
from .models import Competition, CompetitionPortfolio, CompetitionPosition,CompetitionSummary, CompetitionTrade

admin.site.register(Competition)
admin.site.register(CompetitionPortfolio)
admin.site.register(CompetitionPosition)
admin.site.register(CompetitionSummary)
admin.site.register(CompetitionTrade)