from django.contrib import admin

from .models import (
    Stock, PayStackReceipts, Holding, Portfolio, Receipts, WithdrawalOTPRequest, Wallet,WithdrawalRequest,
    Transaction
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