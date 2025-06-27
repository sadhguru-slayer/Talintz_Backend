from django.db import models
from core.models import User

class PaymentMethod(models.Model):
    PAYMENT_TYPES = [
        ('bank_transfer', 'Bank Transfer'),
        ('upi', 'UPI'),
        ('card', 'Credit/Debit Card'),
        ('wallet', 'Platform Wallet'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_methods')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES)
    is_default = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

class PaymentGatewayLog(models.Model):
    transaction = models.ForeignKey('Transaction', on_delete=models.CASCADE)
    gateway_name = models.CharField(max_length=50)
    gateway_transaction_id = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20)
    response_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)