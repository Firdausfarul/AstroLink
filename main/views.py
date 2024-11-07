from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.urls import reverse
import json
import requests
from stellar_sdk import (
    Server, Keypair, TransactionBuilder, Network, Asset, 
    Claimant, ClaimPredicate, Account as StellarAccount
)
from decimal import Decimal
import secrets
from .models import Account, EmailKeyMapping, TemporaryClaim, GiftCardReceipt

from django.contrib.auth.models import User
from django.http import JsonResponse
from stellar_sdk.exceptions import NotFoundError, SdkError
from django.views.decorators.http import require_http_methods
from hashlib import sha256


# Initialize Stellar server
server = Server("https://horizon-testnet.stellar.org")
network_passphrase = Network.TESTNET_NETWORK_PASSPHRASE

ADMIN_KEYPAIR = Keypair.from_raw_ed25519_seed(sha256(b"admin").digest())
CHARITY_KEYPAIR = Keypair.from_raw_ed25519_seed(sha256(b"charitywallet").digest())
GIFTCARD_KEYPAIR = Keypair.from_raw_ed25519_seed(sha256(b"giftcardwallet").digest())

USDC_ISSUER = Keypair.from_raw_ed25519_seed(sha256(b"usdcissuer").digest())

USDC = Asset("USDC", USDC_ISSUER.public_key)

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages

def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out')
    return redirect('home')

def create_account_with_trustline(keypair, asset=None):
    """Create account with initial XLM and optional trustline"""
    try:
        admin_account = server.load_account(ADMIN_KEYPAIR.public_key)
        transaction = TransactionBuilder(
            source_account=admin_account,
            network_passphrase=network_passphrase,
            base_fee=100
        )
        
        # Sponsor account creation and trustline
        transaction.append_begin_sponsoring_future_reserves_op(
            sponsored_id=keypair.public_key,
            source=ADMIN_KEYPAIR.public_key
        )
        
        # Create account with initial 0.1 XLM
        transaction.append_create_account_op(
            destination=keypair.public_key,
            starting_balance="0.1"
        )
        
        # Add USDC trustline by default
        transaction.append_change_trust_op(
            asset=USDC,
            source=keypair.public_key
        )
        
        # Add additional asset trustline if specified
        if asset and asset != Asset.native() and asset != USDC:
            transaction.append_change_trust_op(
                asset=asset,
                source=keypair.public_key
            )
        
        transaction.append_end_sponsoring_future_reserves_op(
            source=keypair.public_key
        )
        
        transaction = transaction.build()
        transaction.sign(ADMIN_KEYPAIR)
        transaction.sign(keypair)
        
        response = server.submit_transaction(transaction)
        return True
    except Exception as e:
        print(f"Error creating account: {str(e)}")
        return False

def home(request):
    """Home page view"""
    return render(request, 'home.html')

@require_http_methods(["GET"])
def check_balance(request):
    """API endpoint to check Stellar balance"""
    try:
        address = request.GET.get('address')
        if not address:
            return JsonResponse({'error': 'Address is required'}, status=400)
            
        account = server.accounts().account_id(address).call()
        balances = {}
        for balance in account['balances']:
            asset_type = balance['asset_type']
            if asset_type == 'native':
                balances['XLM'] = balance['balance']
            else:
                asset_code = balance['asset_code']
                balances[asset_code] = balance['balance']
                
        return JsonResponse({'balances': balances})
    except NotFoundError:
        return JsonResponse({'error': 'Account not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_http_methods(["GET"])
def validate_address(request):
    """API endpoint to validate Stellar address"""
    try:
        address = request.GET.get('address')
        if not address:
            return JsonResponse({'error': 'Address is required'}, status=400)
            
        # Try to create keypair from address
        try:
            Keypair.from_public_key(address)
            return JsonResponse({'valid': True})
        except SdkError:
            return JsonResponse({'valid': False})
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def register(request):
    if request.method == 'POST':
        try:
            # Generate new keypair
            keypair = Keypair.random()
            
            # Create Stellar account
            if not create_account_with_trustline(keypair, USDC):
                messages.error(request, "Failed to create Stellar account")
                return redirect('register')
            
            # Create user and account
            user = User.objects.create_user(
                username=request.POST['email'],
                email=request.POST['email'],
                password=request.POST['password']
            )
            
            Account.objects.create(
                user=user,
                public_key=keypair.public_key,
                private_key=keypair.secret
            )
            
            # Create email mapping
            EmailKeyMapping.objects.create(
                email=request.POST['email'],
                private_key=keypair.secret
            )
            
            messages.success(request, "Account created successfully!")
            return redirect('login')
            
        except Exception as e:
            messages.error(request, f"Registration failed: {str(e)}")
            return redirect('register')
            
    return render(request, 'register.html')

@login_required
def dashboard(request):
    try:
        account = Account.objects.get(user=request.user)
        # Get Stellar account balances
        account_details = server.accounts().account_id(account.public_key).call()
        
        transactions = server.transactions().for_account(account.public_key).order(desc=True).limit(10).call()
        account_details['transactions'] = transactions['_embedded']['records']
        
        context = {
            'account': account,
            'stellar_account': account_details,

        }
        
        return render(request, 'dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f"Failed to load dashboard: {str(e)}")
        return redirect('home')

def claim_money(request, claim_id):

    claim = get_object_or_404(TemporaryClaim, claim_id=claim_id, claimed=False)
    try:
        print(claim.private_key)
        temp_keypair = Keypair.from_secret(claim.private_key)
        # Initialize variables for template
        account_details = server.accounts().account_id(temp_keypair.public_key).call()
        transactions = server.transactions().for_account(temp_keypair.public_key).order(desc=True).limit(10).call()
        account_details['transactions'] = transactions['_embedded']['records']
        #gift_cards = GiftCardReceipt.objects.filter(user=request.user).order_by('-created_at')
            
        context = {
            'account': {
                "public_key": temp_keypair.public_key,
            },
            'stellar_account': account_details,
            'claim_id': claim_id,
            #'gift_cards': gift_cards
        }
        

        return render(request, 'dashboard.html', context)
            
    except Exception as e:
        messages.error(request, f"Failed to load dashboard: {str(e)}")
        return redirect('home')

@login_required
def exchange_for_gift_card(request):
    if request.method == 'POST':
        try:
            amount = Decimal(request.POST['amount'])
            gift_card_type = request.POST['gift_card_type']
            
            account = Account.objects.get(user=request.user)
            source_keypair = Keypair.from_secret(account.private_key)
            
            # First check if account has sufficient USDC balance
            try:
                account_details = server.accounts().account_id(source_keypair.public_key).call()
                usdc_balance = next(
                    (Decimal(b['balance']) for b in account_details['balances'] 
                     if b['asset_type'] != 'native' and b['asset_code'] == 'USDC'),
                    Decimal('0')
                )
                
                if usdc_balance < amount:
                    raise Exception("Insufficient USDC balance")
                
            except NotFoundError:
                raise Exception("Account not found")
            
            # Create payment transaction
            source_account = server.load_account(source_keypair.public_key)
            transaction = (
                TransactionBuilder(
                    source_account=source_account,
                    network_passphrase=network_passphrase,
                    base_fee=100
                )
                .append_payment_op(
                    destination=GIFTCARD_KEYPAIR.public_key,
                    asset=USDC,
                    amount=str(amount)
                )
                .build()
            )
            
            transaction.sign(source_keypair)
            response = server.submit_transaction(transaction)
            
            # Create receipt
            receipt = GiftCardReceipt.objects.create(
                user=request.user,
                gift_card_type=gift_card_type,
                amount=amount,
                transaction_hash=response['hash']
            )
            
            messages.success(request, f"Gift card purchased successfully! Receipt ID: {receipt.id}")
            return redirect('receipt', receipt_id=receipt.id)
            
        except Exception as e:
            messages.error(request, f"Failed to purchase gift card: {str(e)}")
            return redirect('dashboard')
            
    return render(request, 'exchange_gift_card.html')

def send_money(request):
    if request.method == 'POST':
        try:
            amount = Decimal(request.POST['amount'])
            source_asset_type = request.POST.get('source_asset')
            dest_asset_type = request.POST.get('dest_asset')
            destination = request.POST.get('destination')
            
            # Get sender's account
            sender_account = Account.objects.get(user=request.user)
            sender_keypair = Keypair.from_secret(sender_account.private_key)
            
            # Determine assets
            source_asset = USDC if source_asset_type == 'USDC' else Asset.native()
            
            # If dest_asset is specified and different from source_asset, use path payment
            if dest_asset_type and dest_asset_type != source_asset_type:
                dest_asset = USDC if dest_asset_type == 'USDC' else Asset.native()
                
                # Execute path payment
                response = execute_path_payment(
                    request,
                    sender_keypair,
                    source_asset,
                    dest_asset,
                    amount,
                    destination
                )
                messages.success(request, "Money sent via path payment!")
                
            else:
                # Regular payment
                source_account = server.load_account(sender_keypair.public_key)
                transaction = (
                    TransactionBuilder(
                        source_account=source_account,
                        network_passphrase=network_passphrase,
                        base_fee=100
                    )
                    .append_payment_op(
                        destination=destination,
                        asset=source_asset,
                        amount=str(amount)
                    )
                    .build()
                )
                
                transaction.sign(sender_keypair)
                response = server.submit_transaction(transaction)
                messages.success(request, "Money sent successfully!")
            
            return redirect('dashboard')
            
        except Exception as e:
            messages.error(request, f"Failed to send money: {str(e)}")
            return redirect('send_money')
            
    return render(request, 'send_money.html')

@login_required
def send_money_link(request):
    if request.method == 'POST':
        try:
            amount = Decimal(request.POST['amount'])
            asset_code = request.POST['asset_code']
            recipient_email = request.POST.get('recipient_email')
            
            sender_account = Account.objects.get(user=request.user)
            sender_keypair = Keypair.from_secret(sender_account.private_key)
            source_account = server.load_account(sender_keypair.public_key)
            
            asset = USDC if asset_code == 'USDC' else Asset.native()
            
            if True:
                
                temp_keypair = Keypair.random()
                
                transaction = TransactionBuilder(
                    source_account=source_account,
                    network_passphrase=network_passphrase,
                    base_fee=100
                )
                
                transaction.append_begin_sponsoring_future_reserves_op(
                    sponsored_id=temp_keypair.public_key,
                    source=sender_keypair.public_key
                )
                
                transaction.append_create_account_op(
                    destination=temp_keypair.public_key,
                    starting_balance="0.1"
                )
                
                if asset != Asset.native():
                    transaction.append_change_trust_op(
                        asset=asset,
                        source=temp_keypair.public_key
                    )
                    
                    # Send the asset
                    transaction.append_payment_op(
                        destination=temp_keypair.public_key,
                        asset=asset,
                        amount=str(amount)
                    )
                
                transaction.append_end_sponsoring_future_reserves_op(
                    source=temp_keypair.public_key
                )
                
                transaction = transaction.build()
                transaction.sign(sender_keypair)
                transaction.sign(temp_keypair)
                
                response = server.submit_transaction(transaction)
                
                # Create temporary claim record
                claim_id = secrets.token_hex(32)
                TemporaryClaim.objects.create(
                    claim_id=claim_id,
                    private_key=temp_keypair.secret,
                    amount=amount,
                    asset_code=asset_code,
                    claim_link=reverse('claim_money', args=[claim_id])
                )
                
                messages.success(request, f"Money sent! Claim link: {request.build_absolute_uri(reverse('claim_money', args=[claim_id]))}")    
            
            return redirect('dashboard')
            
        except Exception as e:
            messages.error(request, f"Failed to send money: {str(e)}")
            return redirect('send_money')
            
    return render(request, 'send_money.html')

@login_required
def receipt(request, receipt_id):
    receipt = get_object_or_404(GiftCardReceipt, id=receipt_id)
    return render(request, 'receipt.html', {'receipt': receipt})

def faucet(request):
    if request.method == 'POST':
        destination = request.POST.get('destination')
        try:
            # Validate the destination address
            dest_keypair = Keypair.from_public_key(destination)
            
            # Load admin account
            source_account = server.load_account(ADMIN_KEYPAIR.public_key)
            

            # Send XLM and USDC
            source_account = server.load_account(ADMIN_KEYPAIR.public_key)
            transaction = (
                TransactionBuilder(
                    source_account=source_account,
                    network_passphrase=network_passphrase,
                    base_fee=100
                )
                .append_payment_op(
                    destination=destination,
                    asset=Asset.native(),
                    amount="100"
                )
                .append_payment_op(
                    destination=destination,
                    asset=USDC,
                    amount="100"
                )
                .build()
            )
            transaction.sign(ADMIN_KEYPAIR)
            response = server.submit_transaction(transaction)
            
            messages.success(request, "Successfully sent 100 XLM and 100 USDC!")
            return redirect('faucet')
            
        except Exception as e:
            messages.error(request, f"Faucet error: {str(e)}")
            return redirect('faucet')
            
    return render(request, 'faucet.html')

# views.py
from stellar_sdk.operation.path_payment_strict_send import PathPaymentStrictSend
from stellar_sdk.operation.path_payment_strict_receive import PathPaymentStrictReceive
from stellar_sdk import Asset, Server, Keypair, TransactionBuilder, Network
# Define available gift cards
GIFT_CARDS = {
    'INDOSAT_20K': {
        'name': 'Indosat Voucher 20k IDR',
        'cost': 2,  # USDC
        'type': 'MOBILE'
    },
    'STEAM_60K': {
        'name': 'Steam Wallet 60k IDR',
        'cost': 5,  # USDC
        'type': 'GAME'
    },
    'ALFA_50K': {
        'name': 'Alfamart 50k IDR',
        'cost': 5,  # USDC
        'type': 'RETAIL'
    }
}

def get_path_payment_operations(server, source_asset, dest_asset, send_amount=None, receive_amount=None):
    """Get possible path payments between assets"""
    
    try:
        paths = None
        if send_amount:
            # Strict send
            paths = (server.strict_send_paths(
                source_asset=source_asset,
                source_amount=str(send_amount),
                destination=[dest_asset]
            ).call())
        else:
            # Strict receive
            paths = (server.strict_receive_paths(
                source=[source_asset],
                destination_asset=dest_asset,
                destination_amount=str(receive_amount)
            ).call())
        return paths['_embedded']['records']
    except Exception as e:
        print(f"Path finding error: {str(e)}")
        return []
def execute_path_payment(request, account_keypair, source_asset, dest_asset, send_amount, dest_address):
    """Execute a path payment transaction"""
    source_account = server.load_account(account_keypair.public_key)
    paths = get_path_payment_operations(server, source_asset, dest_asset, send_amount=send_amount)
    
    if not paths:
        raise Exception("No payment path found")
        
    path = paths[0]  # Get best path
    
    # Create path payment operation
    path_payment_op = PathPaymentStrictSend(
        destination=dest_address,
        send_asset=source_asset,
        send_amount=str(send_amount),
        dest_asset=dest_asset,
        dest_min=str(float(path['destination_amount']) * 0.99),  # 1% slippage tolerance
        path=path['path']
    )
    
    transaction = (
        TransactionBuilder(
            source_account=source_account,
            network_passphrase=network_passphrase,
            base_fee=100
        )
        .append_operation(path_payment_op)
        .build()
    )
    
    transaction.sign(account_keypair)
    return server.submit_transaction(transaction)

from decimal import Decimal
from stellar_sdk import Server, Asset, Keypair, TransactionBuilder
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

def merge_account(request, claim_id):
    """Merge temporary account to another account"""
    claim = get_object_or_404(TemporaryClaim, claim_id=claim_id, claimed=False)
    if request.method == 'POST':
        try:
            destination = request.POST.get('destination')
            temp_keypair = Keypair.from_secret(claim.private_key)
            
            print(claim.private_key)
            print(temp_keypair.public_key)
            # Load account for sequence number
            temp_account = server.load_account(temp_keypair.public_key)
            
            # Fetch account details including balances
            account_details = server.accounts().account_id(temp_keypair.public_key).call()
            balances = account_details['balances']
            
            # Create transaction builder
            transaction_builder = TransactionBuilder(
                source_account=temp_account,
                network_passphrase=network_passphrase,
                base_fee=100
            )
            
            # 1. Transfer all assets
            for balance in balances:
                if Decimal(balance['balance']) > 0:
                    if balance['asset_type'] == 'native':
                        # Leave minimum balance for operations
                        xlm_amount = Decimal(balance['balance']) - Decimal('1.5')
                        if xlm_amount > 0:
                            transaction_builder.append_payment_op(
                                destination=destination,
                                asset=Asset.native(),
                                amount=str(xlm_amount)
                            )
                    else:
                        asset = Asset(
                            balance['asset_code'],
                            balance['asset_issuer']
                        )
                        transaction_builder.append_payment_op(
                            destination=destination,
                            asset=asset,
                            amount=balance['balance']
                        )
            
            # 2. Remove all trustlines
            for balance in balances:
                if balance['asset_type'] != 'native':
                    asset = Asset(
                        balance['asset_code'],
                        balance['asset_issuer']
                    )
                    transaction_builder.append_change_trust_op(
                        asset=asset,
                        limit="0"
                    )
            
            # 3. Merge account
            transaction_builder.append_account_merge_op(
                destination=destination
            )
            
            # Build and submit transaction
            transaction = transaction_builder.build()
            transaction.sign(temp_keypair)
            response = server.submit_transaction(transaction)
            
            # Mark claim as claimed
            claim.claimed = True
            claim.save()
            
            messages.success(request, "Account successfully merged!")
            return redirect('home')
            
        except Exception as e:
            
            messages.error(request, f"Failed to merge account: {str(e)}")
            return redirect('home.html')
    
    return render(request, 'home.html')

def path_payment(request, claim_id=None):
    """Handle path payment/swap"""
    try:
        if request.method == 'POST':
            source_asset_type = request.POST.get('source_asset')
            dest_asset_type = request.POST.get('dest_asset')
            amount = Decimal(request.POST.get('amount'))
            
            # Get source asset
            if source_asset_type == 'XLM':
                source_asset = Asset.native()
            else:
                source_asset = USDC  # Add more assets as needed
                
            # Get destination asset
            if dest_asset_type == 'XLM':
                dest_asset = Asset.native()
            else:
                dest_asset = USDC
                
            # Get account keypair
            if claim_id:
                claim = get_object_or_404(TemporaryClaim, claim_id=claim_id, claimed=False)
                account_keypair = Keypair.from_secret(claim.private_key)
            else:
                account = Account.objects.get(user=request.user)
                account_keypair = Keypair.from_secret(account.private_key)
                
            # Execute path payment
            response = execute_path_payment(
                request,
                account_keypair,
                source_asset,
                dest_asset,
                amount,
                account_keypair.public_key  # Send to self for swaps
            )
            
            messages.success(request, "Swap executed successfully!")
            
        else:
            messages.error(request, "Invalid request method")
            
    except Exception as e:
        messages.error(request, f"Swap failed: {str(e)}")
        
    if claim_id:
        return redirect('temp_dashboard', claim_id=claim_id)
    return redirect('dashboard')

def buy_gift_card(request, claim_id=None):
    """Handle gift card purchase with path payment"""
    try:
        if request.method == 'POST':
            
            gift_card_code = request.POST.get('gift_card_code')
            gift_card = GIFT_CARDS[gift_card_code]
            source_ass = USDC
            if request.POST.get('source_asset') != 'USDC':
                source_ass = Asset.native()
            # Get account keypair
            if claim_id:
                claim = get_object_or_404(TemporaryClaim, claim_id=claim_id, claimed=False)
                account_keypair = Keypair.from_secret(claim.private_key)
            else:
                account = Account.objects.get(user=request.user)
                account_keypair = Keypair.from_secret(account.private_key)
            
            
            # Execute path payment to gift card wallet
            response = execute_path_payment(
                request,
                account_keypair,
                source_ass,  # Allow payment in any asset
                USDC,
                gift_card['cost'],
                GIFTCARD_KEYPAIR.public_key
            )
            print(response)
            
            # Create receipt
            GiftCardReceipt.objects.create(
                user=request.user if request.user.is_authenticated else None,
                gift_card_type=gift_card['type'],
                amount=gift_card['cost'],
                transaction_hash=response['hash']
            )
            
            messages.success(request, f"Successfully purchased {gift_card['name']}, receipt!")
            
        else:
            messages.error(request, "Invalid request method")
            
    except Exception as e:
        
        messages.error(request, f"Gift card purchase failed: {str(e)}")
        
    if claim_id:
        
        return redirect('temp_dashboard', claim_id=claim_id)
    return redirect('dashboard')