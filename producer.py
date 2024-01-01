import asyncio
import websockets
import json
import random

async def produce_mock_data(websocket, path):
    print(path)
    stock = path.lstrip('/')
    print(stock)

    while True:
        if stock not in stocks:
            print(f"Invalid stock: {stock}")
        else:
            open_price = prices.get(stock, 100)  # Starting open price is 100.
            volume = random.randint(1000, 10000)
            price_change = random.uniform(-20, 20)
            new_price = get_next_price(stock, price_change)
            percentage_change = ((new_price - open_price) / open_price) * 100

            message = json.dumps({
                "stock": stock,
                "open_price": round(open_price, 2),
                "current_price": round(new_price, 2),
                "volume": volume,
                "percentage_change": round(percentage_change, 2)
            })

            print(message)
            await websocket.send(message)

        await asyncio.sleep(10)

def get_next_price(stock, price_change):
    current_price = prices.get(stock, 100)  # Starting price is 100.
    new_price = current_price + price_change
    prices[stock] = new_price
    print(new_price)
    return round(new_price, 2)

stocks = [
    "ABBEYBDS", "ACADEMY", "ACCESSCORP", "AFRIPRUD", "AFRINSURE", "AFROMEDIA", "AIICO", "AIRTELAFRI",
    "ALEX", "ARBICO", "ASOSAVINGS", "ABCTRANS", "AUSTINLAZ", "MANSARD", "BERGER", "BETAGLAS", "BAPLC",
    "BUACEMENT", "BUAFOODS", "CILEASING", "CADBURY", "CAP", "CAPOIL", "CAVERTON", "CHAMPION", "CHAMS",
    "NIDF", "CHELLARAM", "CONOIL", "CHIPLC", "CORNERST", "WAPIC", "CUSTODIAN", "CUTIX", "CWG", "DAARCOMM",
    "DANGCEM", "DANGSUGAR", "DEAPCAP", "DUNLOP", "ETRANZACT", "ETI", "EKOCORP", "ELLAHLAKES", "ETERNA",
    "EUNISELL", "FBNH", "FCMB", "FIDELITYBK", "FIDSON", "FLOURMILL", "FTNCOCOA", "GEREGU", "GLAXOSMITH",
    "GOLDBREW", "GOLDINSURE", "VANLEER", "GTCO", "GUINEAINS", "GUINNESS", "HONYFLOUR", "IKEJAHOTEL", "IMG",
    "INFINITY", "INTBREW", "INTENEGINS", "JAIZBANK", "JAPAULGOLD", "JOHNHOLT", "JULI", "JBERGER", "WAPCO",
    "LASACO", "LEARNAFRCA", "LINKASSURE", "LIVESTOCK", "LIVINGTRUST", "MAYBAKER", "MCNICHOLS", "MEDVIEWAIR",
    "MEYER", "MORISON", "MRS", "MTNN", "MULTITREX", "MULTIVERSE", "MBENEFIT", "NNFM", "NASCON", "NCR",
    "NEIMETH", "NEM", "NESTLE", "NIGERINS", "NESF", "NAHCO", "NB", "ENAMELWA", "NGXGROUP", "NOTORE",
    "NPFMCRFBK", "OANDO", "OKOMUOIL", "OMATEK", "PZ", "PHARMDEKO", "PREMPAINTS", "PRESCO", "PRESTIGE",
    "RTBRISCOE", "RAKUNITY", "REDSTAREX", "REGALINS", "RESORTSAL", "RONCHESS", "ROYALEX", "SCOA", "NSLTECH",
    "SEPLAT", "SFSREIT", "SKYAVN", "SMURFIT", "SOVRENINS", "STACO", "STANBIC", "STDINSURE", "STERLINGNG",
    "SUNUASSUR", "TANTALIZER", "TIP", "THOMASWY", "TOTAL", "TOURIST", "TRANSEXPR", "TRANSCOHOT", "TRANSCORP",
    "TRIPPLEG", "UACN", "UHOMREIT", "UNILEVER", "UBN", "UNIONDICON", "UNHOMES", "UBA", "UCAP", "UNITYBNK",
    "UNIVINSURE", "UPL", "UPDC", "UPDCREIT", "VERITASKAP", "VFDGROUP", "VITAFOAM", "WEMABANK", "ZENITHBANK"
]

prices = {stock: 100.0 for stock in stocks}


start_server = websockets.serve(produce_mock_data, "localhost", 8765)
print('Server started....')

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
