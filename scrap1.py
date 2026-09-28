import os
import re
import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

driver = webdriver.Chrome()

# Navigate to the website
driver.get('https://www.nairaland.com/')

# Define the XPaths to be used
nairid_xpath = "//a[contains(@href, 'nairaland.com/787')]"
linTitle_xpath = "//div[@class='body']/h2"


print('here1')
# Collect the data
results = []
nairid_links = WebDriverWait(driver, 60).until(
    EC.presence_of_all_elements_located((By.XPATH, nairid_xpath))
)

for link in range(len(nairid_links)):
    print('here2',link)
    nairid_links[link].click()

    # Extract information
    name_e = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, linTitle_xpath))
    )
    p_text = driver.find_element(By.XPATH, "//p[@class='nocopy']").text

    p_users = driver.find_element(By.XPATH, "//p[@class='nocopy']").text 
    user_list = [user.strip() for user in p_users.split(',')]
    num_users = len(user_list)

    page_views = driver.find_element(By.XPATH, "//p[@class='bold']")
    views_match = re.search(r'(\d+) Views', page_views.text)
    views_count = int(views_match.group(1)) if views_match else 0

    # Create the data dictionary
    nairPg = {
        'NamTit': name_e.text,
        'Views': views_count,
        'actusers': num_users,
        'guests': re.search(r'(\d+) guest', p_text).group(1) if re.search(r'(\d+) guest', p_text) else ''
    }

    results.append(nairPg)
    driver.back()

# Quit the driver when done
driver.quit()

# Save the data to a CSV file
file_name = 'Nairaland_data.csv'
file_exists = os.path.isfile(file_name)

with open(file_name, 'a', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['NamTit', 'Views', 'actusers', 'guests'])

    # Write header only if the file is newly created
    if not file_exists:
        writer.writeheader()

    # Write the data
    writer.writerows(results)
