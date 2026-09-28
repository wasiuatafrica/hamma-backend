from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class MediaStorage(S3Boto3Storage):
    location = settings.MEDIAFILES_LOCATION
    # Class attributes win over AWS_S3_CUSTOM_DOMAIN. A custom domain makes
    # django-storages return unsigned URLs, which this private bucket rejects.
    custom_domain = None
    querystring_auth = True
    querystring_expire = settings.AWS_S3_PRESIGNED_EXPIRY_SECONDS
