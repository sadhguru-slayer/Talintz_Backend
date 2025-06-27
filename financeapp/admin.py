from django.contrib import admin
from financeapp.models import (
    SubscriptionPlan,
    UserSubscription,
    Wallet,
    WalletTransaction,
    Transaction,
    CommissionTier,
    Commission,
    PaymentMethod,
    PaymentGatewayLog,
    Hold
)

# Register your models here
admin.site.register(SubscriptionPlan)
admin.site.register(UserSubscription)
admin.site.register(Wallet)
admin.site.register(Hold)
admin.site.register(WalletTransaction)
admin.site.register(Transaction)
admin.site.register(CommissionTier)
admin.site.register(Commission)
admin.site.register(PaymentMethod)
admin.site.register(PaymentGatewayLog)