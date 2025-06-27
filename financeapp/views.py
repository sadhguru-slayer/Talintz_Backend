from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum, Q
from decimal import Decimal
from .models import Wallet, WalletTransaction
from django.utils import timezone
import razorpay
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.views import View
import json
from datetime import datetime, timedelta
from core.models import Project, Milestone, Task
from .models.hold import Hold
from .models.transaction import Transaction
from .models.subscription import UserSubscription

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_wallet_balance(request):
    """Get user's wallet balance and recent transactions"""
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    
    # Get recent transactions
    recent_transactions = WalletTransaction.objects.filter(
        wallet=wallet
    ).order_by('-timestamp')[:5]
    
    transactions_data = [{
        'id': str(tx.id),
        'amount': float(tx.amount),
        'type': tx.transaction_type,
        'status': tx.status,
        'timestamp': tx.timestamp.isoformat(),
        'description': tx.description
    } for tx in recent_transactions]

    return Response({
        'balance': float(wallet.balance),
        'hold_balance': float(wallet.hold_balance),
        'currency': wallet.currency,
        'recent_transactions': transactions_data,
        'last_updated': wallet.last_updated.isoformat()
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deposit_funds(request):
    """Deposit funds into wallet"""
    try:
        amount = Decimal(str(request.data.get('amount', 0)))
        description = request.data.get('description', 'Deposit')
        
        if amount <= 0:
            return Response({
                'error': 'Amount must be positive'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        wallet = request.user.wallet
        wallet.deposit(amount, description)
        
        return Response({
            'message': 'Deposit successful',
            'new_balance': float(wallet.balance),
            'transaction_id': wallet.transactions.latest('timestamp').reference_id
        })
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def withdraw_funds(request):
    """Withdraw funds from wallet"""
    try:
        amount = Decimal(str(request.data.get('amount', 0)))
        description = request.data.get('description', 'Withdrawal')
        
        if amount <= 0:
            return Response({
                'error': 'Amount must be positive'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        wallet = request.user.wallet
        wallet.withdraw(amount, description)
        
        return Response({
            'message': 'Withdrawal successful',
            'new_balance': float(wallet.balance),
            'transaction_id': wallet.transactions.latest('timestamp').reference_id
        })
    except ValueError as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_transaction_history(request):
    """Get wallet transaction history with filters"""
    wallet = request.user.wallet
    
    # Get query parameters
    transaction_type = request.GET.get('type')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    limit = int(request.GET.get('limit', 20))
    offset = int(request.GET.get('offset', 0))
    
    # Build query
    transactions = wallet.get_transaction_history()
    
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
    if start_date:
        transactions = transactions.filter(timestamp__gte=start_date)
    if end_date:
        transactions = transactions.filter(timestamp__lte=end_date)
    
    # Get total count
    total_count = transactions.count()
    
    # Apply pagination
    transactions = transactions[offset:offset + limit]
    
    transactions_data = [{
        'id': str(tx.id),
        'reference_id': tx.reference_id,
        'amount': float(tx.amount),
        'type': tx.transaction_type,
        'status': tx.status,
        'timestamp': tx.timestamp.isoformat(),
        'description': tx.description
    } for tx in transactions]
    
    return Response({
        'transactions': transactions_data,
        'total_count': total_count,
        'has_more': (offset + limit) < total_count
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_wallet_order(request):
    """
    Create a Razorpay order for wallet deposit.
    """
    try:
        amount = float(request.data.get('amount'))
        if amount <= 0:
            return Response({'error': 'Amount must be positive.'}, status=400)
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        order = client.order.create({
            "amount": int(amount * 100),  # paise
            "currency": "INR",
            "payment_capture": 1,
            "notes": {
                "user_id": str(request.user.id),
                "purpose": "wallet_deposit"
            }
        })
        return Response({
            "order_id": order['id'],
            "amount": order['amount'],
            "currency": order['currency'],
            "razorpay_key": settings.RAZORPAY_KEY_ID
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_wallet_payment(request):
    """
    Verify Razorpay payment and credit wallet.
    """
    from .models import Wallet, WalletTransaction
    data = request.data
    razorpay_order_id = data.get('razorpay_order_id')
    razorpay_payment_id = data.get('razorpay_payment_id')
    razorpay_signature = data.get('razorpay_signature')
    amount = float(data.get('amount'))

    # Verify signature
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    try:
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }
        client.utility.verify_payment_signature(params_dict)
    except razorpay.errors.SignatureVerificationError:
        return Response({'error': 'Payment verification failed.'}, status=400)

    # Credit wallet (idempotent)
    wallet, _ = Wallet.objects.get_or_create(user=request.user)
    if not WalletTransaction.objects.filter(reference_id=razorpay_payment_id).exists():
        wallet.deposit(amount, description="Wallet deposit via Razorpay", reference_id=razorpay_payment_id)
    return Response({'message': 'Wallet credited successfully.'})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_comprehensive_wallet_details(request):
    """Get detailed wallet information with hold breakdown and transaction history"""
    try:
        wallet = request.user.wallet
        user_role = request.user.role
        
        # Get active holds with details
        active_holds = wallet.get_active_holds().select_related(
            'project', 'milestone', 'obsp_response'
        )
        
        holds_data = []
        for hold in active_holds:
            hold_info = {
                'id': str(hold.id),
                'hold_type': hold.hold_type,
                'amount': float(hold.amount),
                'title': hold.title,
                'description': hold.description,
                'created_at': hold.created_at.isoformat(),
                'expires_at': hold.expires_at.isoformat() if hold.expires_at else None,
                'days_remaining': hold.days_remaining,
                'reference_id': hold.reference_id,
                'metadata': hold.metadata
            }
            
            # Add specific details based on hold type
            if hold.hold_type == 'project_milestone':
                hold_info.update({
                    'project_title': hold.project.title if hold.project else 'Unknown Project',
                    'milestone_title': hold.milestone.title if hold.milestone else 'Unknown Milestone',
                    'project_id': str(hold.project.id) if hold.project else None,
                    'milestone_id': str(hold.milestone.id) if hold.milestone else None,
                })
            elif hold.hold_type == 'obsp_purchase':
                hold_info.update({
                    'obsp_title': hold.obsp_response.template.title if hold.obsp_response else 'Unknown OBSP',
                    'obsp_level': hold.obsp_response.selected_level if hold.obsp_response else None,
                })
            elif hold.hold_type == 'auto_pay_commitment':
                hold_info.update({
                    'auto_pay_details': hold.metadata.get('auto_pay_details', {}),
                })
            
            holds_data.append(hold_info)
        
        # Group holds by type for summary
        holds_summary = {}
        for hold in active_holds:
            hold_type = hold.hold_type
            if hold_type not in holds_summary:
                holds_summary[hold_type] = {
                    'count': 0,
                    'total_amount': Decimal('0.00'),
                    'holds': []
                }
            holds_summary[hold_type]['count'] += 1
            holds_summary[hold_type]['total_amount'] += hold.amount
            holds_summary[hold_type]['holds'].append(str(hold.id))
        
        # Convert to float for JSON serialization
        for hold_type in holds_summary:
            holds_summary[hold_type]['total_amount'] = float(holds_summary[hold_type]['total_amount'])
        
        # Get recent transactions (customize limit as needed)
        recent_transactions = wallet.get_transaction_history(limit=20)
        transactions_data = [{
            'id': str(tx.id),
            'reference_id': tx.reference_id,
            'amount': float(tx.amount),
            'type': tx.transaction_type,
            'status': tx.status,
            'timestamp': tx.timestamp.isoformat(),
            'description': tx.description
        } for tx in recent_transactions]
        
        return Response({
            'basic_info': {
                'balance': float(wallet.balance),
                'hold_balance': float(wallet.hold_balance),
                'total_balance': float(wallet.total_balance),
                'currency': wallet.currency,
                'last_updated': wallet.last_updated.isoformat()
            },
            'holds': {
                'active_holds': holds_data,
                'holds_summary': holds_summary,
                'total_hold_amount': float(wallet.get_total_hold_amount())
            },
            'user_role': user_role,
            'recent_transactions': transactions_data
        })
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def freelancer_wallet_details(request):
    user = request.user
    if not hasattr(user, 'wallet'):
        return Response({'error': 'Wallet not found.'}, status=404)
    wallet = user.wallet

    

    # 1. Holds (project, OBSP stake, etc.)
    holds = Hold.objects.filter(wallet=wallet, status='active')
    # Header Info
    header = {

        'balance': float(wallet.balance),
        'hold_balance': float(wallet.hold_balance),
        'currency': wallet.currency,
        'last_updated': wallet.last_updated.isoformat(),
    }
    holds_data = []
    for hold in holds:
        hold_info = {
            'id': str(hold.id),
            'hold_type': hold.hold_type,
            'amount': float(hold.amount),
            'title': hold.title,
            'description': hold.description,
            'created_at': hold.created_at.isoformat(),
            'reference_id': hold.reference_id,
            'project_title': hold.project.title if hold.project else None,
            'milestone_title': hold.milestone.title if hold.milestone else None,
            'obsp_response_id': str(hold.obsp_response.id) if hold.obsp_response else None,
        }
        holds_data.append(hold_info)

    # 2. Earnings (project, milestone, task payments)
    earnings_qs = Transaction.objects.filter(
        to_user=user,
        payment_type__in=['project', 'milestone', 'task'],
        status='completed'
    ).order_by('-created_at')
    earnings = []
    for tx in earnings_qs:
        earnings.append({
            'id': str(tx.id),
            'amount': float(tx.amount),
            'type': tx.payment_type,
            'description': tx.description,
            'project': tx.project.title if tx.project else None,
            'milestone': tx.milestone.title if tx.milestone else None,
            'task': tx.task.title if tx.task else None,
            'timestamp': tx.created_at.isoformat(),
        })

    # 3. Transactions (Transaction, WalletTransaction, UserSubscription)
    # a. Platform Transactions
    platform_transactions = Transaction.objects.filter(
        Q(from_user=user) | Q(to_user=user)
    ).order_by('-created_at')[:20]
    platform_tx_data = [{
        'id': str(tx.id),
        'amount': float(tx.amount),
        'type': tx.payment_type,
        'direction': 'in' if tx.to_user == user else 'out',
        'description': tx.description,
        'timestamp': tx.created_at.isoformat(),
        'status': tx.status,
    } for tx in platform_transactions]

    # b. Wallet Transactions
    wallet_transactions = WalletTransaction.objects.filter(wallet=wallet).order_by('-timestamp')[:20]
    wallet_tx_data = [{
        'id': str(wtx.id),
        'amount': float(wtx.amount),
        'type': wtx.transaction_type,
        'description': wtx.description,
        'timestamp': wtx.timestamp.isoformat(),
        'status': wtx.status,
    } for wtx in wallet_transactions]

    # c. Subscriptions
    subscriptions = UserSubscription.objects.filter(user=user).order_by('-start_date')[:5]
    subs_data = [{
        'id': str(sub.id),
        'plan': sub.plan.name,
        'start_date': sub.start_date.isoformat(),
        'end_date': sub.end_date.isoformat(),
        'is_active': sub.is_active,
        'auto_renew': sub.auto_renew,
    } for sub in subscriptions]

    return Response({
        'header': header,
        'holds': holds_data,
        'earnings': earnings,
        'transactions': {
            'platform': platform_tx_data,
            'wallet': wallet_tx_data,
            'subscriptions': subs_data,
        }
    })

