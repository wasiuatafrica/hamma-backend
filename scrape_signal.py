from playwright.sync_api import sync_playwright
import json
from pymongo import MongoClient
from playwright.sync_api import sync_playwright
import time

client = MongoClient(
    "mongodb+srv://trademql5:trademql5@trademql5.fmlxv.mongodb.net/",
    tls=True,
    tlsAllowInvalidCertificates=True,
)

db_merged = client["livelake3"]
# collection = db_merged["merged_live_price"]
collection = db_merged["merged_live_price_trdv"]
last_item = collection.find_one(sort=[("_id", -1)])
last_item.pop("_id")

symbols = [symbol for symbol, data in last_item.items()]
symbols.sort(reverse=True)


# Function to scrape TradingView technicals synchronously
def scrape_trading_view_technicals_sync(symbol, tab):
    with sync_playwright() as p:
        # Browser setup
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Navigate to the page
        url = f"https://www.tradingview.com/symbols/{symbol}/technicals/"
        page.goto(url, timeout=0)
        page.wait_for_load_state("domcontentloaded")

        # Click the specified tab
        tab_element = page.query_selector(f"text={tab}")
        if not tab_element:
            print(f"{tab} button not found")
            browser.close()
            return None

        tab_element.click()
        print(f"Clicked {tab} button")
        time.sleep(3)

        # Initialize data structure
        data = {
            "speedometer_data": [],
            "technical_data": {"Oscillators": [], "Moving Averages": [], "Pivots": {}},
        }

        # Get speedometer data
        page.wait_for_selector(".speedometersContainer-kg4MJrFB")
        speedometer_divs = page.query_selector_all(".speedometerWrapper-kg4MJrFB")
        for div in speedometer_divs:
            title_element = div.query_selector(".speedometerTitle-kg4MJrFB")
            if not title_element:
                continue

            title = title_element.inner_text()
            speedometer_body = div.query_selector(".countersWrapper-kg4MJrFB")
            if speedometer_body:
                counter_divs = speedometer_body.query_selector_all(
                    ".counterWrapper-kg4MJrFB"
                )
                sub_data = []
                for counter in counter_divs:
                    counter_title = counter.query_selector(".counterTitle-kg4MJrFB")
                    counter_value = counter.query_selector(".counterNumber-kg4MJrFB")
                    if counter_title and counter_value:
                        counter_title_text = counter_title.inner_text()
                        counter_value_text = counter_value.inner_text()
                        sub_data.append(
                            {
                                "counter_title_text": counter_title_text,
                                "counter_value_text": counter_value_text,
                            }
                        )
                data["speedometer_data"].append({"title": title, "sub_data": sub_data})

        # Get technical data (oscillators, moving averages, and pivots)
        div_containers = page.query_selector_all(
            ".container-hvDpy38G.tabletVertical-hvDpy38G"
        )
        if div_containers:
            for container in div_containers:
                title = container.query_selector(".link-hvDpy38G")
                if title:
                    title_text = title.inner_text()

                    if "Oscillators" in title_text or "Moving Averages" in title_text:
                        table_section = (
                            data["technical_data"]["Oscillators"]
                            if "Oscillators" in title_text
                            else data["technical_data"]["Moving Averages"]
                        )
                        table_div = container.query_selector(".tableWrapper-hvDpy38G")
                        if table_div:
                            headers_tr = table_div.query_selector(".header-hvDpy38G")
                            header_titles = headers_tr.query_selector_all(
                                ".cell-hvDpy38G.phoneLandscape-hvDpy38G"
                            )

                            headers = []
                            if header_titles:
                                for header in header_titles:
                                    header_text = header.inner_text()
                                    headers.append(header_text)

                            body_trs = table_div.query_selector_all(".row-hvDpy38G")
                            for tr in body_trs:
                                body_tds = tr.query_selector_all(
                                    ".cell-hvDpy38G.phoneLandscape-hvDpy38G"
                                )
                                if body_tds:
                                    row_data = {}
                                    for idx, td in enumerate(body_tds):
                                        td_text = td.inner_text()
                                        if idx < len(headers):
                                            row_data[headers[idx]] = td_text
                                    table_section.append(row_data)

                    elif "Pivots" in title_text:
                        table_div = container.query_selector(".tableWrapper-hvDpy38G")
                        if table_div:
                            headers_tr = table_div.query_selector(".header-hvDpy38G")
                            header_titles = headers_tr.query_selector_all(
                                ".cell-hvDpy38G.phoneLandscape-hvDpy38G"
                            )

                            headers = []
                            if header_titles:
                                for header in header_titles:
                                    header_text = header.inner_text()
                                    headers.append(header_text)

                            for indicator in headers[1:]:
                                data["technical_data"]["Pivots"][indicator] = {}

                            body_trs = table_div.query_selector_all(".row-hvDpy38G")
                            for tr in body_trs:
                                body_tds = tr.query_selector_all(
                                    ".cell-hvDpy38G.phoneLandscape-hvDpy38G"
                                )
                                if body_tds:
                                    pivot_level = body_tds[0].inner_text()
                                    for idx, td in enumerate(body_tds[1:], start=1):
                                        td_text = td.inner_text()
                                        indicator = headers[idx]
                                        data["technical_data"]["Pivots"][indicator][
                                            pivot_level
                                        ] = td_text

        browser.close()
        return data


def get_data_sync(symbol):
    tabs = ["1 hour", "1 day", "1 week", "1 month"]
    data = {}

    for tab in tabs:
        period = "_".join(tab.split())
        result = scrape_trading_view_technicals_sync(f"NSENG-{symbol}", tab)

        if result:  # Check if result is not None
            # Clean speedometer data
            for speedometer in result["speedometer_data"]:
                for sub_item in speedometer["sub_data"]:
                    sub_item["counter_value_text"] = sub_item[
                        "counter_value_text"
                    ].replace("\u2212", "-")

            # Clean technical data
            tech_data = result["technical_data"]

            # Clean Oscillators
            for osc in tech_data["Oscillators"]:
                for key, value in osc.items():
                    if isinstance(value, str):
                        osc[key] = value.replace("\u2212", "-")

            # Clean Moving Averages
            for ma in tech_data["Moving Averages"]:
                for key, value in ma.items():
                    if isinstance(value, str):
                        ma[key] = value.replace("\u2212", "-")

            # Clean Pivots
            for indicator, levels in tech_data["Pivots"].items():
                for level, value in levels.items():
                    if isinstance(value, str):
                        tech_data["Pivots"][indicator][level] = value.replace(
                            "\u2212", "-"
                        )

            data[period] = result

    return data


def gather_data_for_symbols_sync(symbols, batch_size=10, delay_between_batches=5):
    all_data = {}

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i : i + batch_size]

        print(f"Processing batch: {batch}")
        for symbol in batch:
            result = get_data_sync(symbol)
            all_data[symbol] = result

        # Delay between batches to avoid hitting rate limits
        if i + batch_size < len(symbols):
            print(f"Waiting for {delay_between_batches} seconds before next batch...")
            time.sleep(delay_between_batches)

    return all_data


def main_sync():
    start_time = time.time()
    data = gather_data_for_symbols_sync(symbols, batch_size=10, delay_between_batches=5)
    end_time = time.time()

    print(f"Total time taken: {end_time - start_time} seconds")
    return data


scraped_data = main_sync()

with open("scraped_data2.json", "w") as json_file:
    json.dump(scraped_data, json_file, indent=4)
