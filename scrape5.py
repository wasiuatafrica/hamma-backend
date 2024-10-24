import asyncio
from playwright.async_api import async_playwright
import json
from multiprocessing import Pool
from itertools import islice
import os
from datetime import datetime
import time


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


async def process_counter(counter):
    try:
        counter_title = await counter.query_selector(".counterTitle-kg4MJrFB")
        counter_value = await counter.query_selector(".counterNumber-kg4MJrFB")
        if counter_title and counter_value:
            title_text = await counter_title.inner_text()
            value_text = await counter_value.inner_text()
            return {
                "counter_title_text": title_text,
                "counter_value_text": value_text,
            }
        return None
    except Exception as e:
        print(f"Error processing counter: {str(e)}")
        return None


async def process_table(container, title_text, is_pivots=False):
    table_div = await container.query_selector(".tableWrapper-hvDpy38G")
    if not table_div:
        return None

    headers_tr = await table_div.query_selector(".header-hvDpy38G")
    header_elements = await headers_tr.query_selector_all(
        ".cell-hvDpy38G.phoneLandscape-hvDpy38G"
    )
    headers = [await header.inner_text() for header in header_elements]

    body_trs = await table_div.query_selector_all(".row-hvDpy38G")

    if is_pivots:
        pivot_data = {header: {} for header in headers[1:]}
        for tr in body_trs:
            cells = await tr.query_selector_all(
                ".cell-hvDpy38G.phoneLandscape-hvDpy38G"
            )
            if cells:
                pivot_level = await cells[0].inner_text()
                for idx, cell in enumerate(cells[1:], start=1):
                    value = await cell.inner_text()
                    pivot_data[headers[idx]][pivot_level] = value
        return pivot_data

    table_data = []
    for tr in body_trs:
        cells = await tr.query_selector_all(".cell-hvDpy38G.phoneLandscape-hvDpy38G")
        if cells:
            row_data = {
                headers[idx]: await cell.inner_text()
                for idx, cell in enumerate(cells)
                if idx < len(headers)
            }
            table_data.append(row_data)

    return table_data


# Unified scraping function for speedometer and oscillator sections
async def scrape_sections(page):
    data = {}
    try:
        await page.wait_for_load_state("networkidle")

        # Speedometer section
        speedometer_data = []
        speedometer_divs = await page.query_selector_all(".speedometerWrapper-kg4MJrFB")
        for div in speedometer_divs:
            title_element = await div.query_selector(".speedometerTitle-kg4MJrFB")
            if not title_element:
                continue

            title = await title_element.inner_text()
            speedometer_body = await div.query_selector(".countersWrapper-kg4MJrFB")
            if speedometer_body:
                counter_divs = await speedometer_body.query_selector_all(
                    ".counterWrapper-kg4MJrFB"
                )
                sub_data = await asyncio.gather(
                    *[process_counter(counter) for counter in counter_divs]
                )
                sub_data = [item for item in sub_data if item]
                speedometer_data.append({"title": title, "sub_data": sub_data})

        data["speedometer"] = speedometer_data

        # Oscillator section
        data.update({"Oscillators": [], "Moving Averages": [], "Pivots": {}})
        div_containers = await page.query_selector_all(
            ".container-hvDpy38G.tabletVertical-hvDpy38G"
        )
        for container in div_containers:
            title_element = await container.query_selector(".link-hvDpy38G")
            if title_element:
                title_text = await title_element.inner_text()
                is_pivots = "Pivots" in title_text
                section_data = await process_table(container, title_text, is_pivots)
                if "Oscillators" in title_text:
                    data["Oscillators"] = section_data
                elif "Moving Averages" in title_text:
                    data["Moving Averages"] = section_data
                elif "Pivots" in title_text:
                    data["Pivots"] = section_data

    except Exception as e:
        print(f"Error in scraping sections: {str(e)}")
        return None

    return data


async def scrape_symbol_data(symbol, tab, context):
    try:
        page = await context.new_page()
        url = f"https://www.tradingview.com/symbols/NSENG-{symbol}/technicals/"
        await page.goto(url)
        tab_element = await page.query_selector(f"text={tab}")
        if tab_element:
            await tab_element.click()
            await asyncio.sleep(1)  # Reduce sleep to 1s
            data = await scrape_sections(page)
            return data
    except Exception as e:
        print(f"Error scraping {symbol} for {tab}: {str(e)}")
        return None
    finally:
        await page.close()


def save_progress(symbol, data):
    filename = "scraping_progress8.json"
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


async def main(symbols):
    start_time = time.time()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        contexts = [
            await browser.new_context() for _ in range(5)
        ]  # Reduce to 5 contexts

        tabs = ["1 hour", "1 day", "1 week", "1 month"]
        results = {}
        tasks = []

        for symbol in symbols:
            for tab in tabs:
                context = contexts[len(tasks) % len(contexts)]
                tasks.append(scrape_symbol_data(symbol, tab, context))

        completed = await asyncio.gather(*tasks)

        for i, symbol in enumerate(symbols):
            print(f"Processing {symbol}")
            results[symbol] = {}
            for j, tab in enumerate(tabs):
                period = "_".join(tab.split())
                results[symbol][period] = completed[i * len(tabs) + j]
            save_progress(symbol, results[symbol])

        for context in contexts:
            await context.close()

        await browser.close()

    end_time = time.time()
    print(f"Total time taken: {end_time - start_time} seconds")


if __name__ == "__main__":
    asyncio.run(main(symbols[:1]))
