# views.py
import os
from typing import Any, Dict

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import CustomUser
from execution.models import DemoPortfolio


class UserManagementView(APIView):
    """Base class for user management views with admin permissions."""

    permission_classes = [IsAdminUser]

    def get_user(self, user_id: int):
        """Helper method to get user object."""
        return get_object_or_404(CustomUser, id=user_id)


class EditUserInfoView(UserManagementView):
    """
    Endpoint for admins to edit user information.
    PUT /api/admin/users/<user_id>/edit/

    Sample Request:
    {
        "firstname": "John",
        "lastname": "Doe",
        "email": "john@example.com",
        "phone": "1234567890",
        "country": "US",
        "city": "New York",
        "address": "123 Main St",
        "bank_name": "Bank Name",
        "account_number": "1234567890",
        "paypal_address": "john@paypal.com"
    }
    """

    def put(self, request, user_id: int) -> Response:
        user = self.get_user(user_id)
        data = request.data

        try:
            # Define fields for each model
            user_fields = ["firstname", "lastname", "email"]
            profile_fields = [
                "phone",
                "country",
                "city",
                "address",
                "bank_name",
                "account_number",
                "paypal_address",
            ]

            # Update user fields
            for field in user_fields:
                if field in data:
                    setattr(user, field, data[field])
            user.save()

            # Update profile fields
            profile = user.profile.first()
            if profile:
                for field in profile_fields:
                    if field in data:
                        setattr(profile, field, data[field])
                profile.save()

            # Prepare response with updated data
            response_data = {
                "id": user.id,
                "firstname": user.firstname,
                "lastname": user.lastname,
                "email": user.email,
                "phone": profile.phone if profile else None,
                "country": profile.country if profile else None,
                "city": profile.city if profile else None,
                "address": profile.address if profile else None,
                "bank_name": profile.bank_name if profile else None,
                "account_number": profile.account_number if profile else None,
                "paypal_address": profile.paypal_address if profile else None,
                "is_active": user.is_active,
                "profile_image": user.profile_image,
                "proof_of_id": user.proof_of_id,
                "proof_of_address": user.proof_of_address,
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e), "message": "Failed to update user information"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ClearKYCImagesView(UserManagementView):
    """
    Endpoint for admins to clear KYC images.
    POST /api/admin/users/<user_id>/clear-kyc/
    """

    def post(self, request, user_id: int) -> Response:
        user = self.get_user(user_id)
        profile = user.profile.first()

        if not profile:
            return Response(
                {"error": "Profile not found", "user_id": user_id},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            profile.proof_of_id = None
            profile.proof_of_address = None

            profile.save()

            # Return updated user data
            response_data = {
                "id": user.id,
                "firstname": user.firstname,
                "lastname": user.lastname,
                "email": user.email,
                "proof_of_id": "",  # Empty string as files are cleared
                "proof_of_address": "",  # Empty string as files are cleared
                "message": "KYC images cleared successfully",
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e), "message": "Failed to clear KYC images"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class DeactivateUserView(UserManagementView):
    """
    Endpoint for admins to deactivate users.
    POST /api/admin/users/<user_id>/deactivate/

    Sample Request:
    {
        "is_active": false
    }
    """

    def post(self, request, user_id: int) -> Response:
        user = self.get_user(user_id)

        try:
            # Allow explicitly setting active status
            is_active = request.data.get("is_active", False)
            user.is_active = is_active
            user.save()

            response_data = {
                "id": user.id,
                "firstname": user.firstname,
                "lastname": user.lastname,
                "email": user.email,
                "is_active": user.is_active,
                "message": f"User {'activated' if is_active else 'deactivated'} successfully",
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e), "message": "Failed to update user status"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class UserTradingAccountsView(UserManagementView):
    """
    Endpoint to show trading accounts belonging to a user.
    GET /api/admin/users/<user_id>/trading-accounts/
    """

    def get(self, request, user_id: int) -> Response:
        user = self.get_user(user_id)

        try:
            trading_accounts = DemoPortfolio.objects.filter(user=user)

            response_data = [
                {
                    "id": account.id,
                    "user_email": account.user.email,
                    "created": account.created.isoformat() if account.created else None,
                    "balance": str(account.balance),
                    "account_name": account.account_name,
                    "account_id": account.account_id,
                    "initial_balance": str(account.initial_balance),
                    "is_prop": account.is_prop,
                    "profit_target": (
                        str(account.profit_target) if account.profit_target else None
                    ),
                    "account_drawdown_limit": (
                        str(account.account_drawdown_limit)
                        if account.account_drawdown_limit
                        else None
                    ),
                    "is_active": account.is_active,
                    "code": account.code,
                    "blown": account.blown,
                    "inactive_by_inactivity": account.inactive_by_inactivity,
                    "activated": account.activated,
                    "receipt_approved": account.receipt_approved,
                    "broker": account.broker,
                    "model_type": account.model_type,
                    "payout": account.payout,
                    "time_to_payout": account.time_to_payout,
                    "target_met": account.target_met,
                    "updated": account.updated.isoformat() if account.updated else None,
                    "balance_based_drawdown": account.balance_based_drawdown,
                    "last_swap_charge_date": (
                        account.last_swap_charge_date.isoformat()
                        if account.last_swap_charge_date
                        else None
                    ),
                    "passed_date": (
                        account.passed_date.isoformat() if account.passed_date else None
                    ),
                    "discount_code": (
                        {
                            "id": account.discount_code.id,
                            "code": account.discount_code.code,
                        }
                        if account.discount_code
                        else None
                    ),
                    "account_type_level": account.account_type_level,
                    "has_hamma": (
                        {
                            "id": account.has_hamma.id,
                            "account_id": account.has_hamma.account_id,
                            "account_name": account.has_hamma.account_name,
                        }
                        if account.has_hamma
                        else None
                    ),
                    "issued_at": (
                        account.issued_at.isoformat() if account.issued_at else None
                    ),
                    "account_type": account.account_type,
                }
                for account in trading_accounts
            ]

            # Add metadata to response
            final_response = {
                "count": len(response_data),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "firstname": user.firstname,
                    "lastname": user.lastname,
                },
                "accounts": response_data,
            }

            return Response(final_response, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e), "message": "Failed to fetch trading accounts"},
                status=status.HTTP_400_BAD_REQUEST,
            )
