from django.contrib import admin
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
ClanMemeberRemoverRequest
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
admin.site.register(CompetitionPosition)
admin.site.register(CompetitionTransaction)