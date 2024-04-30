import re
import requests
import pandas as pd
from bs4 import BeautifulSoup

def extract_emails(text):
    # Regular expression pattern for matching email addresses
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    
    # Find all matches of the pattern in the text
    emails = re.findall(pattern, text)
    
    return [email.lower() for email in emails]  # Convert emails to lowercase

email_set = set()

for i in range(6501,7729):
    url = f"https://www.nairaland.com/1131485/nigerian-stock-exchange-market-pick/{i}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Accept-Language": "en-US,en;q=0.9",
    }
    response = requests.get(url, headers=headers)
    print("Page:", i)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, "html.parser")
        emails = extract_emails(str(soup))

        for email in emails:
            print(email, "from page", i)
            email_set.add(email)
    
    else:
        print("Failed to retrieve the page. Status code:", response.status_code)

# Convert the email set to a DataFrame and save it to an Excel file
email_df = pd.DataFrame(list(email_set), columns=['Email'])
email_df.to_excel("emails10.xlsx", index=False)

print("Email addresses have been written to 'emails.xlsx'")
