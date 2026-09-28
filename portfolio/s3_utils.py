from __future__ import annotations

import logging
from functools import lru_cache
from urllib.parse import unquote, urlparse

import boto3
from botocore.config import Config
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_PRESIGNED_EXPIRY_SECONDS = 86400  # 24 hours


@lru_cache(maxsize=1)
def _get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
        ),
    )


def parse_s3_url(url: str) -> tuple[str, str] | None:
    """Extract (bucket, key) from a virtual-hosted-style S3 URL."""
    if not url:
        return None

    parsed = urlparse(url)
    host = parsed.netloc
    key = unquote(parsed.path.lstrip("/"))
    if not host or not key:
        return None

    if ".s3." in host and host.endswith(".amazonaws.com"):
        bucket = host.split(".s3.", 1)[0]
        return bucket, key

    if host.endswith(".s3.amazonaws.com"):
        bucket = host[: -len(".s3.amazonaws.com")]
        return bucket, key

    return None


def presign_s3_url(url: str | None, expiration: int | None = None) -> str | None:
    """
    Return a presigned GET URL for a private S3 object.
    Non-S3 URLs are returned unchanged.
    """
    if not url:
        return None

    parsed = parse_s3_url(url)
    if not parsed:
        return url

    bucket, key = parsed
    expiry = expiration or getattr(
        settings, "AWS_S3_PRESIGNED_EXPIRY_SECONDS", DEFAULT_PRESIGNED_EXPIRY_SECONDS
    )

    try:
        return _get_s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiry,
        )
    except Exception:
        logger.exception("Failed to presign S3 URL for key %s", key)
        return url
