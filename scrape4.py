import asyncio
from playwright.async_api import async_playwright
import json
from multiprocessing import Pool
from itertools import islice
import os
from datetime import datetime

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


def fix_special_characters(json_data):
    # Decode and encode the JSON data to handle special characters
    fixed_data = json.dumps(
        json_data, ensure_ascii=False, indent=2
    )  # Preserve non-ASCII characters

    return fixed_data


async def scrape_ngx_tech_analysis_speedometer_section(symbol, tab):
    async with async_playwright() as p:
        # Browser setup
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Navigate to the page
        url = f"https://www.tradingview.com/symbols/{symbol}/technicals/"
        await page.goto(url)
        await page.wait_for_load_state("networkidle")

        # Click the "5 minutes" tab
        tab = await page.query_selector(f"text={tab}")
        if not tab:
            print(f"{tab} button not found")
            await browser.close()
            return None

        await tab.click()
        print(f"Clicked {tab} button")
        await asyncio.sleep(5)
        await page.wait_for_selector(".speedometersContainer-kg4MJrFB")

        # Extract data from speedometers
        data = []
        speedometer_divs = await page.query_selector_all(".speedometerWrapper-kg4MJrFB")
        for div in speedometer_divs:
            title_element = await div.query_selector(".speedometerTitle-kg4MJrFB")
            if not title_element:
                print("Speedometer title not found")
                continue

            title = await title_element.inner_text()
            # print(title)
            # data[title] = {}

            speedometer_body = await div.query_selector(".countersWrapper-kg4MJrFB")
            if speedometer_body:
                counter_divs = await speedometer_body.query_selector_all(
                    ".counterWrapper-kg4MJrFB"
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
                        counter_title_text = await counter_title.inner_text()
                        counter_value_text = await counter_value.inner_text()
                        # print(counter_title_text, counter_value_text, ".......")
                        # data[title][counter_title_text] = counter_value_text
                        sub_data.append(
                            {
                                "counter_title_text": counter_title_text,
                                "counter_value_text": counter_value_text,
                            }
                        )
                data.append({"title": title, "sub_data": sub_data})

        await browser.close()
        return data


async def scrape_ngx_tech_analysis_oscilator_section(symbol, tab):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        url = f"https://www.tradingview.com/symbols/{symbol}/technicals/"
        await page.goto(url)
        await page.wait_for_load_state("networkidle")

        tab_element = await page.query_selector(f"text={tab}")
        if not tab_element:
            print(f"{tab} button not found")
            await browser.close()
            return None

        await tab_element.click()
        print(f'Clicked "{tab}" button')
        await asyncio.sleep(5)
        await page.wait_for_selector(".container-hvDpy38G.tabletVertical-hvDpy38G")

        data = {"Oscillators": [], "Moving Averages": [], "Pivots": {}}

        div_containers = await page.query_selector_all(
            ".container-hvDpy38G.tabletVertical-hvDpy38G"
        )
        if div_containers:
            for container in div_containers:
                title = await container.query_selector(".link-hvDpy38G")
                if title:
                    title_text = await title.inner_text()

                    if "Oscillators" in title_text or "Moving Averages" in title_text:
                        table_section = (
                            data["Oscillators"]
                            if "Oscillators" in title_text
                            else data["Moving Averages"]
                        )
                        table_div = await container.query_selector(
                            ".tableWrapper-hvDpy38G"
                        )
                        if table_div:
                            headers_tr = await table_div.query_selector(
                                ".header-hvDpy38G"
                            )
                            header_titles = await headers_tr.query_selector_all(
                                ".cell-hvDpy38G.phoneLandscape-hvDpy38G"
                            )

                            headers = []
                            if header_titles:
                                for header in header_titles:
                                    header_text = await header.inner_text()
                                    headers.append(header_text)

                            body_trs = await table_div.query_selector_all(
                                ".row-hvDpy38G"
                            )
                            for tr in body_trs:
                                body_tds = await tr.query_selector_all(
                                    ".cell-hvDpy38G.phoneLandscape-hvDpy38G"
                                )
                                if body_tds:
                                    row_data = {}
                                    for idx, td in enumerate(body_tds):
                                        td_text = await td.inner_text()
                                        if idx < len(headers):
                                            row_data[headers[idx]] = td_text
                                    table_section.append(row_data)

                    elif "Pivots" in title_text:
                        table_div = await container.query_selector(
                            ".tableWrapper-hvDpy38G"
                        )
                        if table_div:
                            headers_tr = await table_div.query_selector(
                                ".header-hvDpy38G"
                            )
                            header_titles = await headers_tr.query_selector_all(
                                ".cell-hvDpy38G.phoneLandscape-hvDpy38G"
                            )

                            headers = []
                            if header_titles:
                                for header in header_titles:
                                    header_text = await header.inner_text()
                                    headers.append(header_text)

                            for indicator in headers[1:]:  # Skip the "Pivot" column
                                data["Pivots"][indicator] = {}

                            body_trs = await table_div.query_selector_all(
                                ".row-hvDpy38G"
                            )
                            for tr in body_trs:
                                body_tds = await tr.query_selector_all(
                                    ".cell-hvDpy38G.phoneLandscape-hvDpy38G"
                                )
                                if body_tds:
                                    pivot_level = await body_tds[0].inner_text()
                                    for idx, td in enumerate(body_tds[1:], start=1):
                                        td_text = await td.inner_text()
                                        indicator = headers[idx]
                                        data["Pivots"][indicator][pivot_level] = td_text

        await browser.close()
        return data


def save_progress(symbol, data):
    filename = "scraping_progress4.json"
    try:
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                progress = json.load(f)
        else:
            progress = {}

        progress[symbol] = {"data": data, "timestamp": datetime.now().isoformat()}

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving progress for {symbol}: {str(e)}")


def get_data(symbol):
    tabs = ["1 hour", "1 day", "1 week", "1 month"]
    data = {}
    for tab in tabs:
        period = ("_").join(tab.split())
        data[period] = {
            "speedometer": asyncio.run(
                scrape_ngx_tech_analysis_speedometer_section(symbol, tab)
            ),
            "oscilatory_section": asyncio.run(
                scrape_ngx_tech_analysis_oscilator_section(symbol, tab)
            ),
        }
        print(f"Scraped data for {period} for {symbol}")
    return data


for symbol in symbols:
    symbol = f"NSENG-{symbol}"
    print(f"Scraping data for {symbol}")
    scraped_signal = get_data(symbol)
    save_progress(symbol, scraped_signal)
