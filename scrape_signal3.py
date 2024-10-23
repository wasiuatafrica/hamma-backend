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


def batch_symbols(symbols, batch_size=3):
    it = iter(symbols)
    while True:
        batch = list(islice(it, batch_size))
        if not batch:
            break
        yield batch


def save_progress(symbol, data):
    filename = "scraping_progress.json"
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


def fix_special_characters(json_data):
    return json.dumps(json_data, ensure_ascii=False, indent=2)


async def scrape_symbol_data(symbol, tab):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # Common setup
            url = f"https://www.tradingview.com/symbols/NSENG-{symbol}/technicals/"
            await page.goto(url)
            await page.wait_for_load_state("networkidle")

            tab_element = await page.query_selector(f"text={tab}")
            if not tab_element:
                print(f"{tab} button not found for {symbol}")
                return None, None

            await tab_element.click()
            await asyncio.sleep(5)

            # Scrape speedometer section
            await page.wait_for_selector(".speedometersContainer-kg4MJrFB")
            speedometer_data = []
            speedometer_divs = await page.query_selector_all(
                ".speedometerWrapper-kg4MJrFB"
            )

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
                    sub_data = []
                    for counter in counter_divs:
                        counter_title = await counter.query_selector(
                            ".counterTitle-kg4MJrFB"
                        )
                        counter_value = await counter.query_selector(
                            ".counterNumber-kg4MJrFB"
                        )
                        if counter_title and counter_value:
                            sub_data.append(
                                {
                                    "counter_title_text": await counter_title.inner_text(),
                                    "counter_value_text": await counter_value.inner_text(),
                                }
                            )
                    speedometer_data.append({"title": title, "sub_data": sub_data})

            # Scrape oscillator section
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

                        if (
                            "Oscillators" in title_text
                            or "Moving Averages" in title_text
                        ):
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
                                            data["Pivots"][indicator][
                                                pivot_level
                                            ] = td_text

                # [Previous oscillator section code remains the same]
                # ... (keeping the original oscillator section scraping logic)

                return speedometer_data, data

        except Exception as e:
            print(f"Error scraping {symbol} for {tab}: {str(e)}")
            return None, None
        finally:
            await browser.close()


def process_symbol(symbol):
    tabs = ["1 hour", "1 day", "1 week", "1 month"]
    data = {}

    for tab in tabs:
        period = ("_").join(tab.split())
        speed_data, osc_data = asyncio.run(scrape_symbol_data(symbol, tab))

        data[period] = {"speedometer": speed_data, "oscillatory_section": osc_data}

    save_progress(symbol, data)
    return {symbol: data}


def main():
    # Example list of symbols
    # symbols = ["NSENG-ACCESSCORP"] * 200  # Replace with your actual list of 200 symbols

    results = {}
    with Pool(processes=3) as pool:
        for batch in batch_symbols(symbols, 3):
            batch_results = pool.map(process_symbol, batch)
            for result in batch_results:
                results.update(result)

    # Save final results
    with open("final_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
