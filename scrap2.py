from playwright.sync_api import sync_playwright
import re

# Function to extract emails from a given HTML content
def extract_emails(html_content):
    emails = re.findall(r'[\w\.-]+@[\w\.-]+', html_content)
    return emails

# Initialize an empty list to store emails
all_emails = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()

    # Loop through all the pages
    for page_num in range(1, 10):
        url = f"https://www.nairaland.com/1131485/nigerian-stock-exchange-market-pick/{page_num}"
        print(f"Scraping page: {url}")

        try:
            page.goto(url)
            html_content = page.content()

            # Extract emails from the current page
            emails = extract_emails(html_content)
            all_emails.extend(emails)

        except Exception as e:
            print(f"Error scraping page {page_num}: {e}")
            continue

    browser.close()

# Save emails to a text file
with open("emails.txt", "w", encoding="utf-8") as file:
    for email in set(all_emails):  # Remove duplicates
        file.write(email + "\n")

print("Emails saved to emails.txt")