from rest_framework import serializers
from .models import (
    Clan,
JoinClanRequest,
TopClanPayout,
TopTraderPayout,
Competition,
CompetitionPortfolio,
CompetitionSummary,
CreateClanRequest,
ClanNameChangeRequest,
ClanMemeberRemoverRequest
)

class CompetitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Competition
        fields='__all__'

class CompetitionPortfolioSerializers(serializers.ModelSerializer):
    class Meta:
        model = CompetitionPortfolio
    fields=[
        'id',
        'account_name',
        'account_type',
        'country',
        'email',
        'fullname',
        'account_id'
    ]

class CompetitionPortfolioCreateSerializers(serializers.ModelSerializer):
    class Meta:
        model = CompetitionPortfolio
        fields=[
            "id",
            'account_name',
            "account_type",
            "balance",
            # "user"
        ]
        
    

class ClanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clan
        fields = [
            'id',
            'clan_admin',
            'clan_name',
            'community_link',
            'clan_logo',
            'description',
            'member',
            'date_request',
            'members_count',
            'position',
            'top_3_count',
            'profit_comparison'
        ]

        extra_kwargs = {
            'member': {'read_only': True},
            'date_request': {'read_only': True},
        }

class ClanUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Clan
        fields = [
            'community_link',
            'clan_logo',
            'description',
        ]
class ClanNameChangeRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClanNameChangeRequest
        fields = [
            "clan",
            "new_clan_name"
        ]
class ClanMemeberRemoverRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClanMemeberRemoverRequest
        fields = [
            "clan",
            "clan_member_to_remove",
            "reason_for_removal"
        ]

class JoinClanRequestSerializers(serializers.ModelSerializer):
    class Meta:
        model = JoinClanRequest
        fields = [
            'approved',
            'date_request',
            'user',
            'id',
            'clan',
        ]
        extra_kwargs = {
            'approved': {'read_only': True},
            'date_request': {'read_only': True},
            # 'user': {'read_only': True},
        }

class CompetitionSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = CompetitionSummary
        fields = [
            'id',
            'country',
            'email',
            'fullname',
            'clan_name',
            "percent_24hrs",
            "percent_week",
            "clan",
            "user",
            "profit",
            "competition",
            'competition_title',
            "created_at"
        ]
        
class TraderPayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model=TopTraderPayout
        fields= ['id','amount','status','date','paytype']
        
class ClanPayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model=TopClanPayout
        fields= '__all__'
        
class CreateClanSerializer(serializers.ModelSerializer):
    class Meta:
        model=CreateClanRequest
        fields= '__all__'
        
class CreateClanRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreateClanRequest
        fields = '__all__'