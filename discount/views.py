from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from execution.models import DemoPortfolio, DiscountCode

User = get_user_model()


class DiscountCodeSerializer(serializers.ModelSerializer):
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = DiscountCode
        fields = [
            "id",
            "code",
            "discount_percentage",
            "is_active",
            "expiry_date",
            "type",
            "num_of_accounts",
            "created",
            "total_used",
            "user",  # Include the user field
            "acc_size",
            "acc_model",
            "user_email",
        ]

    def get_user_email(self, obj):
        """Return the email of the associated user"""
        return obj.user.email if obj.user else None


class DiscountCodeListCreateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """List all discount codes"""
        discount_codes = DiscountCode.objects.all().order_by("-created")
        serializer = DiscountCodeSerializer(discount_codes, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Create a new discount code, associating it with a user by email"""
        # Extract email from request data
        email = request.data.get("user_email")
        # if not email:
        #     return Response(
        #         {"user_email": ["This field is required."]},
        #         status=status.HTTP_400_BAD_REQUEST,
        #     )

        # Verify that the user exists
        if email:
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response(
                    {"email": ["User with this email does not exist."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            user = None

        # Prepare data for serializer (exclude email)
        data = request.data.copy()
        data.pop("email", None)

        # Validate and create the discount code
        serializer = DiscountCodeSerializer(data=data)
        if serializer.is_valid():
            serializer.save(user=user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DiscountCodeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(DiscountCode, pk=pk)

    def get(self, request, pk):
        """Retrieve a specific discount code"""
        discount_code = self.get_object(pk)
        serializer = DiscountCodeSerializer(discount_code)
        return Response(serializer.data)

    def put(self, request, pk):
        """Update a discount code"""
        discount_code = self.get_object(pk)
        serializer = DiscountCodeSerializer(discount_code, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        """Partially update a discount code"""
        discount_code = self.get_object(pk)
        serializer = DiscountCodeSerializer(
            discount_code, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Delete a discount code"""
        discount_code = self.get_object(pk)
        discount_code.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DiscountCodeValidity(APIView):
    permission_classes = [AllowAny]

    def get(self, request, code, format=None):
        try:
            discount_code = DiscountCode.objects.get(code__iexact=code.strip())
            code_details = {
                "code": discount_code.code,
                "discount_percentage": discount_code.discount_percentage,
                "is_active": discount_code.is_active,
                "expiry_date": discount_code.expiry_date,
                "type": discount_code.type,
                "num_of_accounts": discount_code.num_of_accounts,
                "account_size": discount_code.acc_size,
                "account_model": discount_code.acc_model,
            }

            # Check for expired or inactive codes
            if not discount_code.is_active or (
                discount_code.expiry_date and discount_code.expiry_date < timezone.now()
            ):
                return Response(
                    {
                        "valid": False,
                        "details": code_details,
                        "error": "Code is expired",
                    },
                    status=status.HTTP_200_OK,
                )

            # Handle 'prop' and 'personal-prop' type discount codes
            if discount_code.type in ["prop", "personal-prop"]:
                accounts = DemoPortfolio.objects.filter(
                    discount_code=discount_code
                ).count()

                if discount_code.num_of_accounts:
                    if accounts < discount_code.num_of_accounts:
                        # For personal-prop, validate that the code belongs to the authenticated user if provided
                        if (
                            discount_code.type == "personal-prop"
                            and request.user.is_authenticated
                        ):
                            if (
                                discount_code.user
                                and discount_code.user != request.user
                            ):
                                return Response(
                                    {
                                        "valid": False,
                                        "details": code_details,
                                        "error": "Code not found!",
                                    },
                                    status=status.HTTP_200_OK,
                                )

                        return Response(
                            {"valid": True, "details": code_details, "error": None},
                            status=status.HTTP_200_OK,
                        )
                else:
                    return Response(
                        {"valid": True, "details": code_details, "error": None},
                        status=status.HTTP_200_OK,
                    )
                return Response(
                    {
                        "valid": False,
                        "details": code_details,
                        "error": "Account limit reached",
                    },
                    status=status.HTTP_200_OK,
                )

            return Response(
                {
                    "valid": False,
                    "details": code_details,
                    "error": "Invalid discount code type",
                },
                status=status.HTTP_200_OK,
            )

        except DiscountCode.DoesNotExist:
            return Response(
                {"valid": False, "error": "Discount code not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
