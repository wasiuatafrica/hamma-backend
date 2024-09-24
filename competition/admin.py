from django.contrib import admin
from execution.models import CompetitionCumulativeMarketReturns, CompetitionMarketReturns
from .models import (
    Clan,
JoinClanRequest,
TopClanPayout,
TopTraderPayout,
Notification,
Competition,
CompetitionPortfolio,
CompetitionSummary,
CreateClanRequest,
ClanCompetitionSummary,
TopClanMembersPayout,
TopClanMembersPayoutImg,
TopClanPayoutButtonShows,
TopTraderPayoutButtonShows,
CompetitionPosition,
CompetitionTransaction,
ClanNameChangeRequest,
ClanMemeberRemoverRequest,
CompetitionCumulativeReturns2,
CompetitionDailyReturns2,
CompetitionCumulativeReturns,
CompetitionDailyReturns,
)
# Register your models here.
admin.site.register(ClanNameChangeRequest)
admin.site.register(ClanMemeberRemoverRequest)
admin.site.register(Competition)
admin.site.register(CompetitionPortfolio)
admin.site.register(Clan)

class JoinClanRequestAdmin(admin.ModelAdmin):
    # List the fields you want to display in the admin panel
    list_display = ('user', 'clan', 'approved', 'date_request')
    
    # Add a filter for the 'approved' field
    list_filter = ('approved',)  # You can add more filters if needed
    search_fields = ['user__email']

# Register the ModelAdmin
admin.site.register(JoinClanRequest, JoinClanRequestAdmin)

# admin.site.register(JoinClanRequest)
admin.site.register(TopClanPayout)
admin.site.register(TopTraderPayout)
admin.site.register(Notification)
admin.site.register(CompetitionSummary)
admin.site.register(ClanCompetitionSummary)
admin.site.register(CreateClanRequest)
admin.site.register(TopClanMembersPayout)
admin.site.register(TopClanMembersPayoutImg)
admin.site.register(TopClanPayoutButtonShows)
admin.site.register(TopTraderPayoutButtonShows)

class CompetitionPositionAdmin(admin.ModelAdmin):
    search_fields = ['portfolio__user__email']
    list_display = ('portfolio', 'status', 'created', 'updated',)
    list_filter = ('status',)
admin.site.register(CompetitionPosition,CompetitionPositionAdmin)

admin.site.register(CompetitionTransaction)

class CompetitionCumulativeReturns2Admin(admin.ModelAdmin):
    search_fields = ['user__email']

admin.site.register(CompetitionCumulativeReturns2,CompetitionCumulativeReturns2Admin)

class CompetitionDailyReturns2Admin(admin.ModelAdmin):
    search_fields = ['user__email']
    list_display = ('user', 'portfolio_returns','market_returns','created',)

admin.site.register(CompetitionDailyReturns2,CompetitionDailyReturns2Admin)
admin.site.register(CompetitionCumulativeMarketReturns)
admin.site.register(CompetitionMarketReturns)