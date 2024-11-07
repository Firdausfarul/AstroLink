from django.db import models
from django.contrib.auth.models import User

class Account(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    public_key = models.CharField(max_length=56)
    private_key = models.CharField(max_length=56)
    created_at = models.DateTimeField(auto_now_add=True)

class EmailKeyMapping(models.Model):
    email = models.EmailField(unique=True)
    private_key = models.CharField(max_length=56)
    created_at = models.DateTimeField(auto_now_add=True)

class TemporaryClaim(models.Model):
    claim_id = models.CharField(max_length=64, unique=True)
    private_key = models.CharField(max_length=56, null=True, blank=True)  # Made optional for claimable balance
    email = models.EmailField(null=True, blank=True)  # Added for claimable balance recipient
    balance_id = models.CharField(max_length=72, null=True, blank=True)  # Added for claimable balance ID
    amount = models.DecimalField(max_digits=20, decimal_places=7)
    asset_code = models.CharField(max_length=12)
    created_at = models.DateTimeField(auto_now_add=True)
    claimed = models.BooleanField(default=False)
    claim_link = models.CharField(max_length=200)

class GiftCardReceipt(models.Model):
    GIFT_CARD_TYPES = [
        ('AMAZON', 'Amazon Gift Card'),
        ('STEAM', 'Steam Wallet'),
        ('MOBILE', 'Mobile Recharge')
    ]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    gift_card_type = models.CharField(max_length=20, choices=GIFT_CARD_TYPES)
    amount = models.DecimalField(max_digits=20, decimal_places=7)
    transaction_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)