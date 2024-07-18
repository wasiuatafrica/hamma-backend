import requests
import boto3
from io import BytesIO
import cairosvg
from PIL import Image
from urllib.parse import urlparse
from django.conf import settings
from portfolio.models import Stock

AWS_ACCESS_KEY_ID = settings.AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY = settings.AWS_SECRET_ACCESS_KEY
AWS_REGION = settings.AWS_S3_REGION_NAME
AWS_BUCKET = settings.AWS_STORAGE_BUCKET_NAME

def contains_svg(url):
    try:
        parsed_url = urlparse(url)
        path = parsed_url.path
        return path.lower().endswith('.svg')
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

class ConvertOthersToJpeg:
    def __init__(self, image_url, s3_key, stock):
        self.image_url = image_url
        self.s3_key = s3_key
        self.AWS_ACCESS_KEY_ID = AWS_ACCESS_KEY_ID
        self.AWS_SECRET_ACCESS_KEY = AWS_SECRET_ACCESS_KEY
        self.AWS_REGION = AWS_REGION
        self.AWS_BUCKET = AWS_BUCKET
        self.stock = stock
        self.process_image()

    def download_image_to_memory(self, url):
        response = requests.get(url)
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', '').lower()
        if 'image' not in content_type:
            raise ValueError(f"The URL '{url}' does not point to an image file.")
        return BytesIO(response.content), content_type

    def convert_to_jpeg(self, image_content, image_format):
        image = Image.open(image_content)
        jpeg_output = BytesIO()
        image.save(jpeg_output, format='JPEG', quality=95)  # High-quality parameter
        jpeg_output.seek(0)
        return jpeg_output

    def upload_file_to_s3(self, file_content, bucket_name, s3_key):
        s3 = boto3.client('s3', aws_access_key_id=self.AWS_ACCESS_KEY_ID, aws_secret_access_key=self.AWS_SECRET_ACCESS_KEY)
        s3.upload_fileobj(
            file_content,
            bucket_name,
            s3_key,
            ExtraArgs={'ContentType': 'image/jpeg'}
        )
        s3_url = f"https://{bucket_name}.s3.{self.AWS_REGION}.amazonaws.com/{s3_key}"
        return s3_url

    def process_image(self):
        try:
            image_content, image_format = self.download_image_to_memory(self.image_url)
            jpeg_content = self.convert_to_jpeg(image_content, image_format)
            uploaded_url = self.upload_file_to_s3(jpeg_content, self.AWS_BUCKET, self.s3_key)
            self.stock.logo_url = uploaded_url
            self.stock.converted_jpeg = True
            self.stock.save()
            print(f"Uploaded JPEG file to S3 with URL: {uploaded_url}")
        except ValueError as e:
            print(e)
        except Exception as e:
            print(f"Error: {e}")

class ConvertFromSVGToJpeg:
    def __init__(self, image_url, s3_key, stock):
        self.image_url = image_url
        self.s3_key = s3_key
        self.AWS_ACCESS_KEY_ID = AWS_ACCESS_KEY_ID
        self.AWS_SECRET_ACCESS_KEY = AWS_SECRET_ACCESS_KEY
        self.AWS_REGION = AWS_REGION
        self.AWS_BUCKET = AWS_BUCKET
        self.stock = stock
        self.process_image()

    def download_svg_to_memory(self, url):
        response = requests.get(url)
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', '')
        if 'image/svg+xml' not in content_type:
            raise ValueError(f"The URL '{url}' does not point to an SVG file.")
        return BytesIO(response.content)

    def convert_svg_to_jpeg(self, svg_content):
        png_output = BytesIO()
        cairosvg.svg2png(file_obj=svg_content, write_to=png_output, dpi=300, output_width=1024, output_height=1024)
        png_output.seek(0)
        image = Image.open(png_output)
        jpeg_output = BytesIO()
        image.save(jpeg_output, format='JPEG', quality=95)  # High-quality parameter
        jpeg_output.seek(0)
        return jpeg_output

    def upload_file_to_s3(self, file_content, bucket_name, s3_key):
        s3 = boto3.client('s3', aws_access_key_id=self.AWS_ACCESS_KEY_ID, aws_secret_access_key=self.AWS_SECRET_ACCESS_KEY)
        s3.upload_fileobj(
            file_content,
            bucket_name,
            s3_key,
            ExtraArgs={'ContentType': 'image/jpeg'}
        )
        s3_url = f"https://{bucket_name}.s3.{self.AWS_REGION}.amazonaws.com/{s3_key}"
        return s3_url

    def process_image(self):
        try:
            svg_content = self.download_svg_to_memory(self.image_url)
            jpeg_content = self.convert_svg_to_jpeg(svg_content)
            uploaded_url = self.upload_file_to_s3(jpeg_content, self.AWS_BUCKET, self.s3_key)
            self.stock.logo_url = uploaded_url
            self.stock.converted_jpeg = True
            self.stock.save()
            print(f"Uploaded JPEG file to S3 with URL: {uploaded_url}")
        except ValueError as e:
            print(e)
        except Exception as e:
            print(f"Error: {e}")

def run_process(url, stock):
    is_svg = contains_svg(url)
    s3_key = f'new_stock_images/image_{stock.symbol}.jpg'
    if is_svg:
        print(True)
        converter = ConvertFromSVGToJpeg(url, s3_key, stock)
    else:
        print(False)
        converter = ConvertOthersToJpeg(url, s3_key, stock)
