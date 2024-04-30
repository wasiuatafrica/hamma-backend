from pyexpat.errors import messages
from django.contrib import admin

from .models import (
    Stock, PayStackReceipts, Receipts, WithdrawalOTPRequest, Wallet,
    Transaction,  Alert, AlertAI, AlertAITracker,  Conversation, Message, DemoTransaction
)


class StockAdmin(admin.ModelAdmin):
    search_fields = ['symbol']
    
admin.site.register(Stock, StockAdmin)
admin.site.register(PayStackReceipts)
# admin.site.register(Holding)
# admin.site.register(Portfolio)
admin.site.register(Receipts)
admin.site.register(WithdrawalOTPRequest)
admin.site.register(Wallet)
# admin.site.register(WithdrawalRequest)
class TransactionAdmin(admin.ModelAdmin):
    # Displaying all relevant fields in the list view
    list_display = ('user', 'transaction_type', 'amount', 'date', 'status', 'channel')

    # Allowing filtering by the 'status' field
    list_filter = ('status',)

    # Adding a search field for searching by user email
    search_fields = ['user__email']

# Registering the admin model with the Transaction model
admin.site.register(Transaction, TransactionAdmin)
# admin.site.register(Trade)
admin.site.register(Alert)
admin.site.register(AlertAI)
admin.site.register(AlertAITracker)
# admin.site.register(DemoTrade)
# admin.site.register(DemoHolding)
# admin.site.register(DemoPortfolio)
admin.site.register(Message)
admin.site.register(Conversation)
admin.site.register(DemoTransaction)
# admin.site.register(Position)
# admin.site.register(DemoPosition)