import requests
import boto3
from io import BytesIO
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM
import cairosvg
import os
import requests
from PIL import Image
from urllib.parse import urlparse
from django.conf import settings
from portfolio.models import Stock

AWS_ACCESS_KEY_ID= settings.AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=settings.AWS_SECRET_ACCESS_KEY
AWS_REGION=settings.AWS_S3_REGION_NAME
AWS_BUCKET=settings.AWS_STORAGE_BUCKET_NAME


def contains_svg(url):
    """
    Check if the URL contains an SVG file.

    :param url: str - The URL to be checked
    :return: bool - True if the URL contains an SVG file, False otherwise
    """
    try:
        # Parse the URL
        parsed_url = urlparse(url)
        # Extract the path from the parsed URL
        path = parsed_url.path

        # Check if the path ends with '.svg'
        return path.lower().endswith('.svg')
    except Exception as e:
        # Log the error if necessary
        print(f"An error occurred: {e}")
        return False

class ConvertOthersToPng:

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
        response.raise_for_status()  # Check if the request was successful
        content_type = response.headers.get('Content-Type', '').lower()
        if 'image' not in content_type:
            raise ValueError(f"The URL '{url}' does not point to an image file.")
        return BytesIO(response.content), content_type

    def convert_to_png(self, image_content, image_format):
        # Open image from memory
        image = Image.open(image_content)

        # Convert to PNG in memory
        png_output = BytesIO()
        image.save(png_output, format='PNG')
        png_output.seek(0)  # Reset file pointer to beginning
        return png_output

    def upload_file_to_s3(self, file_content, bucket_name, s3_key):
        s3 = boto3.client('s3', aws_access_key_id=self.AWS_ACCESS_KEY_ID, aws_secret_access_key=self.AWS_SECRET_ACCESS_KEY)
        # Upload PNG content to S3 with explicit content type
        s3.upload_fileobj(
            file_content,
            bucket_name,
            s3_key,
            ExtraArgs={'ContentType': 'image/png'}
        )
        s3_url = f"https://{bucket_name}.s3.{self.AWS_REGION}.amazonaws.com/{s3_key}"
        return s3_url

    def process_image(self):
        try:
            # Download the image file to memory
            image_content, image_format = self.download_image_to_memory(self.image_url)

            # Convert the image content to PNG in memory
            png_content = self.convert_to_png(image_content, image_format)

            # Upload the PNG content to S3 with the correct content type
            uploaded_url = self.upload_file_to_s3(png_content, self.AWS_BUCKET, self.s3_key)
            self.stock.logo_url =uploaded_url
            self.stock.converted_png = True
            self.stock.save()
            print(f"Uploaded PNG file to S3 with URL: {uploaded_url}")

        except ValueError as e:
            print(e)  # Handle the case where the URL is not an image file or other errors
        except Exception as e:
            print(f"Error: {e}")  # Handle any other exceptions during processing

class ConvertFromSVGToPng:

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
        response.raise_for_status()  # Check if the request was successful
        content_type = response.headers.get('Content-Type', '')
        if 'image/svg+xml' not in content_type:
            raise ValueError(f"The URL '{url}' does not point to an SVG file.")
        return BytesIO(response.content)

    def convert_svg_to_png(self, svg_content):
        # Convert SVG to PNG using cairosvg
        png_output = BytesIO()
        cairosvg.svg2png(file_obj=svg_content, write_to=png_output)
        png_output.seek(0)  # Reset file pointer to beginning
        return png_output

    def upload_file_to_s3(self, file_content, bucket_name, s3_key):
        s3 = boto3.client('s3', aws_access_key_id=self.AWS_ACCESS_KEY_ID, aws_secret_access_key=self.AWS_SECRET_ACCESS_KEY)
        # Upload PNG content to S3 with explicit content type
        s3.upload_fileobj(
            file_content,
            bucket_name,
            s3_key,
            ExtraArgs={'ContentType': 'image/png'}
        )
        s3_url = f"https://{bucket_name}.s3.{self.AWS_REGION}.amazonaws.com/{s3_key}"
        return s3_url

    def process_image(self):
        try:
            # Download the SVG file to memory
            svg_content = self.download_svg_to_memory(self.image_url)

            # Convert the SVG content to PNG in memory
            png_content = self.convert_svg_to_png(svg_content)

            # Upload the PNG content to S3 with the correct content type
            uploaded_url = self.upload_file_to_s3(png_content, self.AWS_BUCKET, self.s3_key)
            self.stock.logo_url = uploaded_url
            self.stock.converted_png = True
            self.stock.save()
            print(f"Uploaded PNG file to S3 with URL: {uploaded_url}")

        except ValueError as e:
            print(e)  # Handle the case where the URL is not an SVG file or other errors
        except Exception as e:
            print(f"Error: {e}")  # Handle any other exceptions during processing

def run_process(url, stock):
    is_svg = contains_svg(url)
    s3_key = f'new_stock_images/image_{stock.symbol}.png'  # Specify your desired key structure
    if is_svg:
        print(True) 
        converter = ConvertFromSVGToPng(url, s3_key, stock)
    else:
        print(False)
        converter = ConvertOthersToPng(url, s3_key, stock)

