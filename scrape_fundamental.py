import requests
from bs4 import BeautifulSoup
import json
import asyncio
from playwright.async_api import async_playwright
import time
import re
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()


def clean_value(value):
    cleaned = re.sub(r"[\u200e\u200f\u202a-\u202e\u202f]", "", value)
    cleaned = cleaned.replace("\xa0", "").replace("\u00a0", "")
    cleaned = cleaned.replace(",", "")
    return cleaned.strip()


def scrape_tradingview_asset_overview_key_stat_section(symbol):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    keystat_data = []

    url = f"https://www.tradingview.com/symbols/{symbol}/"

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return f"Failed to retrieve the page. Status code: {response.status_code}"

    soup = BeautifulSoup(response.text, "html.parser")

    # Find the div with the specific data-container-name
    key_stats_div = soup.find("div", attrs={"data-container-name": "key-stats-id"})
    if key_stats_div:
        container_GRoarMHL = key_stats_div.find(
            "div", attrs={"class": "container-GRoarMHL"}
        )
        if container_GRoarMHL:
            # Find all divs with the class block-GgmpMpKr
            block_GgmpMpKr_list = container_GRoarMHL.find_all(
                "div", class_="block-GgmpMpKr container-lQwbiR8R"
            )

            # Iterate over the found div elements
            for block_GgmpMpKr in block_GgmpMpKr_list:
                # Find all title and value elements inside each block_GgmpMpKr div
                keystat_titles = block_GgmpMpKr.find_all(
                    "div", class_="apply-overflow-tooltip label-GgmpMpKr"
                )
                keystat_values = block_GgmpMpKr.find_all(
                    "div", class_="apply-overflow-tooltip value-GgmpMpKr"
                )

                # Pair titles with values and add to keystat_data
                for title, value in zip(keystat_titles, keystat_values):
                    # Find the unit span within the value div
                    unit_span = value.find("span", class_="measureUnit-nIcy61xx")
                    unit = unit_span.text.strip() if unit_span else ""

                    # Remove the unit from the value if it exists
                    value_text = clean_value(value.text)
                    if unit:
                        value_text = value_text.replace(unit, "").strip()

                    data_dict = {
                        "title": title.text.strip(),
                        "value": value_text,
                        "unit": unit,
                    }
                    keystat_data.append(data_dict)

            return keystat_data
        else:
            print("container-GRoarMHL not found within key stats div.")
    else:
        print("Key stats div not found - asset overview.")

    return None


# def scrape_tradingview_asset_overview_about_asset_section(symbol):
#     headers = {
#         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
#     }
#     keystat_data = []

#     url = f"https://www.tradingview.com/symbols/{symbol}/"

#     response = requests.get(url, headers=headers)

#     if response.status_code != 200:
#         return f"Failed to retrieve the page. Status code: {response.status_code}"

#     soup = BeautifulSoup(response.text, "html.parser")

#     # Find the div with the specific data-container-name
#     about_asset_section_div = soup.find(
#         "div", attrs={"data-container-name": "company-info-id"}
#     )
#     if about_asset_section_div:
#         container_GRoarMHL = about_asset_section_div.find(
#             "div", attrs={"class": "container-GRoarMHL"}
#         )
#         if container_GRoarMHL:
#             # Find all divs with the class block-GgmpMpKr
#             block_GgmpMpKr_list = container_GRoarMHL.find_all(
#                 "div", class_="block-GgmpMpKr"
#             )

#             # Iterate over the found div elements
#             for block_GgmpMpKr in block_GgmpMpKr_list:
#                 # Find all title and value elements inside each block_GgmpMpKr div
#                 keystat_titles = block_GgmpMpKr.find_all(
#                     "div", class_="apply-overflow-tooltip label-GgmpMpKr"
#                 )
#                 keystat_values = block_GgmpMpKr.find_all(
#                     "div", class_="apply-overflow-tooltip value-GgmpMpKr"
#                 )

#                 # Pair titles with values and add to keystat_data
#                 for title, value in zip(keystat_titles, keystat_values):
#                     data_dict = {"title": title.text.strip(), "value": value.text}
#                     keystat_data.append(data_dict)

#             return keystat_data
#         else:
#             print("container-GRoarMHL not found within key stats div.")
#     else:
#         print("Key stats div not found.")

#     return None


async def scrape_tradingview_asset_overview_upcoming_earnings_section(symbol):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        url = f"https://www.tradingview.com/symbols/{symbol}/"
        await page.goto(url)

        # Wait for the content to load
        await page.wait_for_selector(".container-lu7Cy9jC", timeout=30000)

        # Additional wait to ensure dynamic content is loaded
        await asyncio.sleep(5)

        keystat_data = await page.evaluate(
            """
              () => {
                  function cleanValue(value) {
                      // Remove Unicode control characters and whitespace characters
                      let cleaned = value.replace(/[\u200e\u200f\u202a-\u202e\u202f]/g, '');
                      // Remove non-breaking space and other whitespace characters
                      cleaned = cleaned.replace(/\u00a0/g, '');
                      return cleaned.trim();
                  }
                  const data = [];
                  const container = document.querySelector('.container-lu7Cy9jC');
                  if (container) {
                      const blocks = container.querySelectorAll('.block-GgmpMpKr');
                      blocks.forEach(block => {
                          const title = block.querySelector('.apply-overflow-tooltip.label-GgmpMpKr');
                          const value = block.querySelector('.apply-overflow-tooltip.value-GgmpMpKr');
                          if (title && value) {
                              data.push({
                                  title: cleanValue(title.textContent.trim()),
                                  value: cleanValue(value.textContent.trim())
                              });
                          }
                      });
                  }
                  return data;
              }
          """
        )

        await browser.close()
        return keystat_data


async def scrape_tradingview_asset_financials_statistics_table_head_section(symbol):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        url = f"https://www.tradingview.com/symbols/{symbol}/financials-statistics-and-ratios/?statistics-period=FY"
        await page.goto(url)

        # Wait for the content to load
        await page.wait_for_selector(".container-vKM0WfUu", timeout=30000)

        # Additional wait to ensure dynamic content is loaded
        await asyncio.sleep(5)

        # Corrected page.evaluate without using a string
        keystat_data = await page.evaluate(
            """
            () => {
                let title = "";
                const data = [];
                const titleContainer = document.querySelector('.filling-OWKkVLyj');

                if (titleContainer) {
                    const titleElement = titleContainer.querySelector('.firstColumn-OWKkVLyj');
                    if (titleElement) {
                        title = titleElement.textContent.trim();
                    }
                }

                // Get the title values
                const titleValues = document.querySelector('.values-OWKkVLyj.values-AtxjAQkN');
                if (titleValues) {
                    // Loop through the value containers
                    const valueContainers = titleValues.querySelectorAll('.container-OxVAcLqi');
                    valueContainers.forEach(valueContainer => {
                        const valueElement = valueContainer.querySelector('.value-OxVAcLqi');
                        const subValElement = valueContainer.querySelector('.subvalue-OxVAcLqi');
                        const value = valueElement ? valueElement.textContent.trim() : '';
                        const subVal = subValElement ? subValElement.textContent.trim() : '';

                        if (value || subVal) {
                            data.push({
                                value: value,
                                subVal: subVal
                            });
                        }
                    });
                }

                return {title, data};
            }
        """
        )

        await browser.close()
        return keystat_data


async def scrape_tradingview_asset_financials_statistics_valuation_ration_section(
    symbol,
):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        url = f"https://www.tradingview.com/symbols/{symbol}/financials-statistics-and-ratios/?statistics-period=FY"
        await page.goto(url)

        # Wait for the content to load
        await page.wait_for_selector(".container-vKM0WfUu", timeout=30000)

        # Additional wait to ensure dynamic content is loaded
        await asyncio.sleep(5)

        keystat_data = await page.evaluate(
            """() => {
            function cleanValue(value) {
                // Remove Unicode control characters and whitespace characters
                let cleaned = value.replace(/[\u200e\u200f\u202a-\u202e\u202f]/g, '');
                // Remove non-breaking space and other whitespace characters
                cleaned = cleaned.replace(/\u00a0/g, '');
                return cleaned.trim();
            }

            const data = {};
            const titleSection = {
              "KeyStats": ['Total common shares outstanding'],
              "ValuationRatios": ['Price to earnings ratio', 'Price to sales ratio', 'Price to cash flow ratio', 'Price to book ratio', 'Enterprise value'],
              "LiquidityRatios": ['Current ratio', 'Asset turnover', 'Cash & due from banks to total deposits', 'Loan losses reserves to total loans', 'Non-performing loans to common equity','Non-performing loans to loan loss reserves','Non-performing loans to total loans','Demand deposits to total deposits', 'Loan losses (actual) to total loans','Loan losses (actual) to loan loss reserve','Loan loss coverage ratio' ],
              "ProfitabilityRatios":['Return on assets %', 'Return on equity %', 'Return on invested capital %', 'Operating margin %', 'Net margin %','Non-interest income to total revenue %','Net interest income to average total deposits %','Net interest income to earning assets %', 'Total interest expense to interest bearing liabs %' ],
              "SolvencyRatios": ["Debt to assets ratio","Debt to equity ratio","Long term debt to total assets ratio", "Long term debt to total equity ratio", "Total deposits to total assets", "Gross Loans to total assets", "Invested assets to total assets", "Loan loss reserves to total assets", "Common equity to total deposits", "Invested assets to total deposits", "Invested assets and net loans to total deposits", "Gross Loans to total deposits", "Loan loss reserves to total capital", "Savings deposits to total deposits"],
              "Other":["Tier 1 capital ratio %", "Tier 2 capital ratio %", "Total capital ratio %", "Common equity tier 1 ratio %"]
            };

            // Loop through the titleSection object
            for (const [sectionKey, sections] of Object.entries(titleSection)) {
                data[sectionKey] = [];  // Initialize array for each section
                for (const section of sections) {
                    const sectionElement = document.querySelector(`[data-name="${section}"]`);
                    if (sectionElement) {
                        const title = sectionElement.querySelector('.titleText-C9MdAMrq.withLink-C9MdAMrq.apply-overflow-tooltip').textContent.trim();
                        const valueContainers = sectionElement.querySelectorAll('.container-OxVAcLqi');
                        const subData = [];

                        if (valueContainers.length > 0) {
                            valueContainers.forEach(valueContainer => {
                                const value = valueContainer.querySelector('.value-OxVAcLqi');
                                const valueText = value ? value.textContent.trim() : '';
                                subData.push(cleanValue(valueText));
                            });
                            data[sectionKey].push({ title, subData });
                        }
                    }
                }
            }

            return data;
        }"""
        )

        await browser.close()
        return keystat_data


def scrape_tradingview_asset_overview_employees_section(symbol):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    keystat_data = []

    url = f"https://www.tradingview.com/symbols/{symbol}/"

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return f"Failed to retrieve the page. Status code: {response.status_code}"

    soup = BeautifulSoup(response.text, "html.parser")

    # Find the div with the specific data-container-name
    employee_section_div = soup.find(
        "div", attrs={"data-container-name": "employees-section"}
    )
    if employee_section_div:
        container_GRoarMHL = employee_section_div.find(
            "div", attrs={"class": "container-GRoarMHL"}
        )
        if container_GRoarMHL:
            # Find all divs with the class block-GgmpMpKr
            block_GgmpMpKr_list = container_GRoarMHL.find_all(
                "div", class_="block-GgmpMpKr container-lQwbiR8R"
            )

            # Iterate over the found div elements
            for block_GgmpMpKr in block_GgmpMpKr_list:
                # Find all title and value elements inside each block_GgmpMpKr div
                keystat_titles = block_GgmpMpKr.find_all(
                    "div", class_="apply-overflow-tooltip label-GgmpMpKr"
                )
                keystat_values = block_GgmpMpKr.find_all(
                    "div", class_="apply-overflow-tooltip value-GgmpMpKr"
                )

                # Pair titles with values and add to keystat_data
                for title, value in zip(keystat_titles, keystat_values):
                    # Find the unit span within the value div
                    unit_span = value.find("span", class_="measureUnit-nIcy61xx")
                    unit = unit_span.text.strip() if unit_span else ""

                    # Remove the unit from the value if it exists
                    value_text = clean_value(value.text)
                    if unit:
                        value_text = value_text.replace(unit, "").strip()

                    data_dict = {
                        "title": title.text.strip(),
                        "value": value_text,
                        "unit": unit,
                    }
                    keystat_data.append(data_dict)

            return keystat_data
        else:
            print("container-GRoarMHL not found within key stats div.")
    else:
        print("Key stats div not found. employees")

    return None


def get_stock_information(symbol):
    overview_key_stats = scrape_tradingview_asset_overview_key_stat_section(symbol)
    # overview_about_asset = scrape_tradingview_asset_overview_about_asset_section(symbol)
    # Correct method call using self
    overview_upcoming_earnings = asyncio.run(
        scrape_tradingview_asset_overview_upcoming_earnings_section(symbol)
    )
    financial_section_table_head_section = asyncio.run(
        scrape_tradingview_asset_financials_statistics_table_head_section(symbol)
    )
    financial_section_stat_page = asyncio.run(
        scrape_tradingview_asset_financials_statistics_valuation_ration_section(symbol)
    )
    overview_employee_stat = scrape_tradingview_asset_overview_employees_section(symbol)

    return {
        # "symbol": symbol,
        "overview_key_stats": overview_key_stats,  # Updated variable name
        # "overview_about_asset": overview_about_asset,  # Updated variable name
        "overview_upcoming_earnings": overview_upcoming_earnings,  # Updated variable name
        "financial_section_table_head_section": financial_section_table_head_section,
        "financial_section_stat_page": financial_section_stat_page,
        "overview_employee_stat": overview_employee_stat,
    }


# symbols = [
#     "ABBEYBDS",
#     "ACADEMY",
#     "ACCESSCORP",
#     "AFRIPRUD",
#     "AFRINSURE",
#     "AFROMEDIA",
#     "AIICO",
#     "AIRTELAFRI",
#     "ALEX",
#     "ARBICO",
#     "ASOSAVINGS",
#     "ABCTRANS",
#     "AUSTINLAZ",
#     "MANSARD",
#     "BERGER",
#     "BETAGLAS",
#     "BAPLC",
#     "BUACEMENT",
#     "BUAFOODS",
#     "CILEASING",
#     "CADBURY",
#     "CAP",
#     "CAPOIL",
#     "CAVERTON",
#     "CHAMPION",
#     "CHAMS",
#     "NIDF",
#     "CHELLARAM",
#     "CONOIL",
#     "CHIPLC",
#     "CORNERST",
#     "WAPIC",
#     "CUSTODIAN",
#     "CUTIX",
#     "CWG",
#     "DAARCOMM",
#     "DANGCEM",
#     "DANGSUGAR",
#     "DEAPCAP",
#     "DUNLOP",
#     "ETRANZACT",
#     "ETI",
#     "EKOCORP",
#     "ELLAHLAKES",
#     "ETERNA",
#     "EUNISELL",
#     "FBNH",
#     "FCMB",
#     "FIDELITYBK",
#     "FIDSON",
#     "FLOURMILL",
#     "FTNCOCOA",
#     "GEREGU",
#     "GLAXOSMITH",
#     "GOLDBREW",
#     "GOLDINSURE",
#     "VANLEER",
#     "GTCO",
#     "GUINEAINS",
#     "GUINNESS",
#     "HONYFLOUR",
#     "IKEJAHOTEL",
#     "IMG",
#     "INFINITY",
#     "INTBREW",
#     "INTENEGINS",
#     "JAIZBANK",
symbols = [
    "JAPAULGOLD",
    "JOHNHOLT",
    "JULI",
    "JBERGER",
    "WAPCO",
    "LASACO",
    "LEARNAFRCA",
    "LINKASSURE",
    "LIVESTOCK",
    "LIVINGTRUST",
    "MAYBAKER",
    "MCNICHOLS",
    "MEDVIEWAIR",
    "MEYER",
    "MORISON",
    "MRS",
    "MTNN",
    "MULTITREX",
    "MULTIVERSE",
    "MBENEFIT",
    "NNFM",
    "NASCON",
    "NCR",
    "NEIMETH",
    "NEM",
    "NESTLE",
    "NIGERINS",
    "NESF",
    "NAHCO",
    "NB",
    "ENAMELWA",
    "NGXGROUP",
    "NOTORE",
    "NPFMCRFBK",
    "OANDO",
    "OKOMUOIL",
    "OMATEK",
    "PZ",
    "PHARMDEKO",
    "PREMPAINTS",
    "PRESCO",
    "PRESTIGE",
    "RTBRISCOE",
    "RAKUNITY",
    "REDSTAREX",
    "REGALINS",
    "RESORTSAL",
    "RONCHESS",
    "ROYALEX",
    "SCOA",
    "NSLTECH",
    "SEPLAT",
    "SFSREIT",
    "SKYAVN",
    "SMURFIT",
    "SOVRENINS",
    "STACO",
    "STANBIC",
    "STDINSURE",
    "STERLINGNG",
    "SUNUASSUR",
    "TANTALIZER",
    "TIP",
    "THOMASWY",
    "TOTAL",
    "TOURIST",
    "TRANSEXPR",
    "TRANSCOHOT",
    "TRANSCORP",
    "TRIPPLEG",
    "UACN",
    "UHOMREIT",
    "UNILEVER",
    "UBN",
    "UNIONDICON",
    "UNHOMES",
    "UBA",
    "UCAP",
    "UNITYBNK",
    "UNIVINSURE",
    "UPL",
    "UPDC",
    "UPDCREIT",
    "VERITASKAP",
    "VFDGROUP",
    "VITAFOAM",
    "WEMABANK",
    "ZENITHBANK",
]


def main():
    client = MongoClient(
        os.environ.get("MONGO_STRING"), tls=True, tlsAllowInvalidCertificates=True
    )

    db = client["ngxfundamentals"]
    for symbol in symbols:
        try:
            data = get_stock_information(f"NSENG-{symbol}")
            print("data fetched for", symbol)
            if data:
                collection = db[symbol]
                collection.insert_one(data)
                print(f"Inserted data for {symbol}")
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")


main()
