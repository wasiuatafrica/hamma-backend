from pyexpat.errors import messages
from django.contrib import admin

from .models import (
    Stock, PayStackReceipts, Holding, Portfolio, Receipts, WithdrawalOTPRequest, Wallet,WithdrawalRequest,
    Transaction, Trade, Alert, AlertAI, AlertAITracker, DemoHolding, DemoPortfolio, DemoTrade, Conversation, Message
)

admin.site.register(Stock)
admin.site.register(PayStackReceipts)
admin.site.register(Holding)
admin.site.register(Portfolio)
admin.site.register(Receipts)
admin.site.register(WithdrawalOTPRequest)
admin.site.register(Wallet)
admin.site.register(WithdrawalRequest)
admin.site.register(Transaction)
admin.site.register(Trade)
admin.site.register(Alert)
admin.site.register(AlertAI)
admin.site.register(AlertAITracker)
admin.site.register(DemoTrade)
admin.site.register(DemoHolding)
admin.site.register(DemoPortfolio)
admin.site.register(Message)
admin.site.register(Conversation)