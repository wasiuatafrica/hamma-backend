import asyncio
import json
import multiprocessing
import os
import random
import time
from datetime import datetime
from functools import partial

from playwright.async_api import async_playwright
from pymongo import MongoClient

# MongoDB setup
client = MongoClient(
    "mongodb+srv://ft9jatraders_db_user:HnyOs6KBOwGKjJmy@reducebill.yxn3gnr.mongodb.net/",
    tls=True,
    tlsAllowInvalidCertificates=True,
)

# db_merged = client["livelake3"]
# collection = db_merged["merged_live_price"]
# last_item = collection.find_one(sort=[("_id", -1)])
# last_item.pop("_id")

# symbols = [symbol for symbol, data in last_item.items()]
# symbols.sort(reverse=True)
# print(symbols)
symbols = [
    "ZENITHBANK",
    "WEMABANK",
    "WAPIC",
    "WAPCO",
    "VITAFOAM",
    "VFDGROUP",
    "VERITASKAP",
    "VANLEER",
    "UPL",
    "UPDCREIT",
    "UPDC",
    "UNIVINSURE",
    "UNITYBNK",
    "UNIONDICON",
    "UNILEVER",
    "UNHOMES",
    "UHOMREIT",
    "UCAP",
    "UBA",
    "UACN",
    "TRIPPLEG",
    "TRANSPOWER",
    "TRANSEXPR",
    "TRANSCORP",
    "TRANSCOHOT",
    "TOURIST",
    "TOTAL",
    "TIP",
    "THOMASWY",
    "TANTALIZER",
    "SUNUASSUR",
    "STERLINGNG",
    "STDINSURE",
    "STANBIC",
    "STACO",
    "SOVRENINS",
    "SMURFIT",
    "SKYAVN",
    "SFSREIT",
    "SEPLAT",
    "SCOA",
    "RTBRISCOE",
    "ROYALEX",
    "RONCHESS",
    "REGALINS",
    "REDSTAREX",
    "PZ",
    "PRESTIGE",
    "PRESCO",
    "PREMPAINTS",
    "PHARMDEKO",
    "OMATEK",
    "OKOMUOIL",
    "OANDO",
    "NSLTECH",
    "NPFMCRFBK",
    "NOTORE",
    "NNFM",
    "NIDF",
    "NGXGROUP",
    "NESTLE",
    "NEM",
    "NEIMETH",
    "NCR",
    "NB",
    "NASCON",
    "NAHCO",
    "MULTIVERSE",
    "MULTITREX",
    "MTNN",
    "MRS",
    "MORISON",
    "MEYER",
    "MEDVIEWAIR",
    "MECURE",
    "MCNICHOLS",
    "MBENEFIT",
    "MAYBAKER",
    "MANSARD",
    "LIVINGTRUST",
    "LIVESTOCK",
    "LINKASSURE",
    "LEARNAFRCA",
    "LASACO",
    "JULI",
    "JOHNHOLT",
    "JBERGER",
    "JAPAULGOLD",
    "JAIZBANK",
    "INTENEGINS",
    "INTBREW",
    "INFINITY",
    "IMG",
    "IKEJAHOTEL",
    "HONYFLOUR",
    "GUINNESS",
    "GUINEAINS",
    "GTCO",
    "GOLDINSURE",
    "GOLDBREW",
    "GEREGU",
    "FTNCOCOA",
    "FLOURMILL",
    "FIDSON",
    "FIDELITYBK",
    "FFUNCAPWFF",
    "FFUNCAPMMF",
    "FFUNCAPEQF",
    "FFUNCAPEBF",
    "FFUNCAPBLF",
    "FFUNCAPBDF",
    "FFSFSFIXED",
    "FFLEGYUBFD",
    "FFLEGYMMFD",
    "FFLEGYEYFD",
    "FFLEGYDTFD",
    "FFIONEVGIF",
    "FFIONEVBF",
    "FFIONEABMM",
    "FFFSDHCIF",
    "FFFSDHCGF",
    "FFFRONTIER",
    "FFFBNMMF",
    "FFFBNFIF",
    "FFFBNBALF",
    "FCMB",
    "FBNH",
    "EUNISELL",
    "ETRANZACT",
    "ETI",
    "ETERNA",
    "ENAMELWA",
    "ELLAHLAKES",
    "EKOCORP",
    "DUNLOP",
    "DEAPCAP",
    "DANGSUGAR",
    "DANGCEM",
    "DAARCOMM",
    "CWG",
    "CUTIX",
    "CUSTODIAN",
    "CORNERST",
    "CONOIL",
    "CONHALLPLC",
    "CILEASING",
    "CHELLARAM",
    "CHAMS",
    "CHAMPION",
    "CAVERTON",
    "CAPOIL",
    "CAP",
    "CADBURY",
    "BUAFOODS",
    "BUACEMENT",
    "BETAGLAS",
    "BERGER",
    "BAPLC",
    "AVAIF",
    "AUSTINLAZ",
    "ASOSAVINGS",
    "ARADEL",
    "ALEX",
    "AIRTELAFRI",
    "AIICO",
    "AFROMEDIA",
    "AFRIPRUD",
    "AFRINSURE",
    "ACCESSCORP",
    "ACADEMY",
    "ABCTRANS",
    "ABBEYBDS",
]

# Create progress directory if it doesn't exist
PROGRESS_DIR = "scraping_progress"
os.makedirs(PROGRESS_DIR, exist_ok=True)


async def random_delay():
    await asyncio.sleep(random.uniform(1, 3))


async def get_browser_context(playwright, user_agent=None):
    browser = await playwright.chromium.launch(
        headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
    )

    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent=user_agent
        or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    )

    return browser, context


async def scrape_trading_view_technicals(symbol, tab, max_retries=3):
    for attempt in range(max_retries):
        browser = None
        context = None
        page = None

        try:
            async with async_playwright() as p:
                try:
                    # Initialize browser with more options
                    browser = await p.chromium.launch(
                        headless=True,
                        # args=[
                        #     "--no-sandbox",
                        #     "--disable-setuid-sandbox",
                        #     "--disable-dev-shm-usage",
                        #     "--disable-accelerated-2d-canvas",
                        #     "--disable-gpu",
                        #     "--window-size=1920,1080",
                        # ],
                    )

                    # if not browser:
                    #     print(f"Failed to launch browser for {symbol}")
                    #     continue
                    # print("browser")

                    # Initialize context with more options
                    context = await browser.new_context(
                        # viewport={"width": 1920, "height": 1080},
                        # user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                        # ignore_https_errors=True,
                        # java_script_enabled=True,
                    )
                    # print("context")

                    # if not context:
                    #     print(f"Failed to create context for {symbol}")
                    #     continue

                    # Create new page
                    page = await context.new_page()
                    # print("page")
                    # if not page:
                    #     print(f"Failed to create page for {symbol}")
                    #     continue

                    # Set various timeouts
                    # await page.set_default_navigation_timeout(60000)
                    # await page.set_default_timeout(60000)

                    # Navigate to the page
                    url = f"https://www.tradingview.com/symbols/{symbol}/technicals/"
                    print(f"Navigating to {url}")

                    await page.goto(url, wait_until="networkidle", timeout=60000)
                    # if not response:
                    #     print(f"Failed to get response for {symbol}")
                    #     continue

                    # if response.status != 200:
                    #     print(f"Got status {response.status} for {symbol}")
                    #     continue

                    # Wait for page load
                    await page.wait_for_load_state("domcontentloaded")
                    # await asyncio.sleep(3)  # Additional wait time

                    # Check if page loaded correctly
                    # title = await page.title()
                    # if not title or "Error" in title:
                    #     print(f"Page didn't load correctly for {symbol}: {title}")
                    #     continue

                    # Find and click tab
                    tab_element = await page.query_selector(f"text={tab}")
                    if not tab_element:
                        print(f"{tab} button not found for {symbol}")
                        continue

                    await tab_element.click()
                    print(f"Clicked {tab} button for {symbol}")
                    await asyncio.sleep(3)

                    # Initialize data structure
                    data = {
                        "speedometer_data": [],
                        "technical_data": {
                            "Oscillators": [],
                            "Moving Averages": [],
                            "Pivots": {},
                        },
                    }

                    # Scrape speedometer data
                    try:
                        await page.wait_for_selector(
                            ".speedometersContainer-kg4MJrFB"  # , timeout=10000
                        )
                        speedometer_divs = await page.query_selector_all(
                            ".speedometerWrapper-kg4MJrFB"
                        )
                        for div in speedometer_divs:
                            title_element = await div.query_selector(
                                ".speedometerTitle-kg4MJrFB"
                            )
                            if not title_element:
                                continue

                            title = await title_element.inner_text()
                            speedometer_body = await div.query_selector(
                                ".countersWrapper-kg4MJrFB"
                            )
                            if speedometer_body:
                                counter_divs = (
                                    await speedometer_body.query_selector_all(
                                        ".counterWrapper-kg4MJrFB"
                                    )
                                )
                                sub_data = []
                                for counter in counter_divs:
                                    counter_title = await counter.query_selector(
                                        ".counterTitle-kg4MJrFB"
                                    )
                                    counter_value = await counter.query_selector(
                                        ".counterNumber-kg4MJrFB"
                                    )
                                    if counter_title and counter_value:
                                        counter_title_text = (
                                            await counter_title.inner_text()
                                        )
                                        counter_value_text = (
                                            await counter_value.inner_text()
                                        )
                                        sub_data.append(
                                            {
                                                "counter_title_text": counter_title_text,
                                                "counter_value_text": counter_value_text.replace(
                                                    "\u2212", "-"
                                                ),
                                            }
                                        )
                                data["speedometer_data"].append(
                                    {"title": title, "sub_data": sub_data}
                                )
                    except Exception as e:
                        print(f"Error scraping speedometer data for {symbol}: {str(e)}")

                    # Scrape technical data
                    try:
                        div_containers = await page.query_selector_all(
                            ".container-hvDpy38G.tabletVertical-hvDpy38G"
                        )
                        if div_containers:
                            for container in div_containers:
                                title = await container.query_selector(".link-hvDpy38G")
                                if title:
                                    title_text = await title.inner_text()

                                    if (
                                        "Oscillators" in title_text
                                        or "Moving Averages" in title_text
                                    ):
                                        table_section = (
                                            data["technical_data"]["Oscillators"]
                                            if "Oscillators" in title_text
                                            else data["technical_data"][
                                                "Moving Averages"
                                            ]
                                        )
                                        await process_table(container, table_section)
                                    elif "Pivots" in title_text:
                                        await process_pivots(
                                            container, data["technical_data"]["Pivots"]
                                        )
                    except Exception as e:
                        print(f"Error scraping technical data for {symbol}: {str(e)}")

                    return data
                except Exception as e:
                    print(
                        f"Error processing {symbol} on attempt {attempt + 1}: {str(e)}"
                    )
                    if attempt == max_retries - 1:
                        print(f"Failed to scrape {symbol} after {max_retries} attempts")
                        return None
                    delay = min(5 * (2**attempt), 30)
                    await asyncio.sleep(delay)
                    continue

        except Exception as e:
            print(f"Attempt {attempt + 1} failed for {symbol}: {str(e)}")
            if attempt == max_retries - 1:
                print(f"Failed to scrape {symbol} after {max_retries} attempts")
                return None
            delay = min(5 * (2**attempt), 30)
            await asyncio.sleep(delay)
        finally:
            if browser:
                await browser.close()


async def process_table(container, table_section):
    table_div = await container.query_selector(".tableWrapper-hvDpy38G")
    if table_div:
        headers_tr = await table_div.query_selector(".header-hvDpy38G")
        header_titles = await headers_tr.query_selector_all(
            ".cell-hvDpy38G.phoneLandscape-hvDpy38G"
        )

        headers = []
        if header_titles:
            for header in header_titles:
                header_text = await header.inner_text()
                headers.append(header_text)

        body_trs = await table_div.query_selector_all(".row-hvDpy38G")
        for tr in body_trs:
            body_tds = await tr.query_selector_all(
                ".cell-hvDpy38G.phoneLandscape-hvDpy38G"
            )
            if body_tds:
                row_data = {}
                for idx, td in enumerate(body_tds):
                    td_text = (await td.inner_text()).replace("\u2212", "-")
                    if idx < len(headers):
                        row_data[headers[idx]] = td_text
                table_section.append(row_data)


async def process_pivots(container, pivots_data):
    table_div = await container.query_selector(".tableWrapper-hvDpy38G")
    if table_div:
        headers_tr = await table_div.query_selector(".header-hvDpy38G")
        header_titles = await headers_tr.query_selector_all(
            ".cell-hvDpy38G.phoneLandscape-hvDpy38G"
        )

        headers = []
        if header_titles:
            for header in header_titles:
                header_text = await header.inner_text()
                headers.append(header_text)

        for indicator in headers[1:]:
            pivots_data[indicator] = {}

        body_trs = await table_div.query_selector_all(".row-hvDpy38G")
        for tr in body_trs:
            body_tds = await tr.query_selector_all(
                ".cell-hvDpy38G.phoneLandscape-hvDpy38G"
            )
            if body_tds:
                pivot_level = await body_tds[0].inner_text()
                for idx, td in enumerate(body_tds[1:], start=1):
                    td_text = (await td.inner_text()).replace("\u2212", "-")
                    indicator = headers[idx]
                    pivots_data[indicator][pivot_level] = td_text


async def get_data(symbol):
    tabs = ["1 hour", "1 day", "1 week", "1 month"]
    data = {}

    for tab in tabs:
        period = "_".join(tab.split())
        result = await scrape_trading_view_technicals(f"NSENG-{symbol}", tab)
        if result:
            data[period] = result

        # Save progress after each period
        save_symbol_progress(symbol, data)

        await random_delay()

    return data


def save_symbol_progress(symbol, data):
    filename = os.path.join(PROGRESS_DIR, f"{symbol}_progress.json")
    with open(filename, "w") as f:
        json.dump(data, f)


async def gather_data_for_symbols(
    symbols_subset, batch_size=3, delay_between_batches=10
):
    all_data = {}

    for i in range(0, len(symbols_subset), batch_size):
        batch = symbols_subset[i : i + batch_size]
        print(f"Processing batch: {batch}")

        try:
            tasks = [get_data(symbol) for symbol in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for symbol, result in zip(batch, results):
                if isinstance(result, Exception):
                    print(f"Error processing {symbol}: {str(result)}")
                    continue
                all_data[symbol] = result

        except Exception as e:
            print(f"Batch processing error: {str(e)}")

        print(f"Waiting for {delay_between_batches} seconds before next batch...")
        await asyncio.sleep(delay_between_batches)

    return all_data


async def process_symbol_batch(symbols_subset):
    return await gather_data_for_symbols(symbols_subset)


def run_async_batch(symbols_subset):
    return asyncio.run(process_symbol_batch(symbols_subset))


def main():
    start_time = time.time()

    # Split symbols into chunks for multiprocessing
    num_processes = min(multiprocessing.cpu_count(), 4)  # Limit to 4 processes max
    chunk_size = len(symbols) // num_processes
    symbol_chunks = [
        symbols[i : i + chunk_size] for i in range(0, len(symbols), chunk_size)
    ]

    # Create pool and run processes
    with multiprocessing.Pool(processes=num_processes) as pool:
        results = pool.map(run_async_batch, symbol_chunks)

    # Combine results
    combined_data = {}
    for result in results:
        combined_data.update(result)

    end_time = time.time()
    print(f"Total time taken: {end_time - start_time} seconds")

    # Save final results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"trading_view_data_{timestamp}.json", "w") as f:
        json.dump(combined_data, f)

    return combined_data


if __name__ == "__main__":
    scraped_data = main()
    scraped_data = main()
