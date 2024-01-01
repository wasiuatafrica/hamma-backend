import asyncio
import json
import random
import websockets
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

# List of stocks
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

# Dictionary to keep track of current prices
prices = {stock: 100.0 for stock in stocks}

# Authentication token
AUTH_TOKEN = "Ab$455"

async def update_prices():
    """Background task to update mock prices"""
    print('Updating prices...')
    while True:
        for stock in stocks:
            print(f"updating {stock} price")
            price_change = random.uniform(-3, 3)
            prices[stock] += round(price_change,2)
            print
        await asyncio.sleep(5)  # Update every second

async def produce_mock_data(websocket, path):
    # Simple authentication check
    print('producing....')
    try:
        auth_token = await websocket.recv()
        if auth_token != AUTH_TOKEN:
            await websocket.close(code=1008, reason="Invalid token")
            return
    except websockets.exceptions.ConnectionClosed:
        return
    
    stock = path.lstrip('/')
    if stock not in stocks:
        await websocket.close(code=1008, reason="Invalid stock")
        return
    print(f'connetion for {stock} made')
    try:
        
        print('Entering loop ....')
        while True:
            # open_price = prices[stock]
            # new_price = prices[stock]
            # volume = random.randint(1000, 10000)
            # percentage_change = round(((new_price - open_price) / open_price) * 100, 2)
            
            # message = json.dumps({
            #     "stock": stock,
            #     "open_price": round(open_price, 2),
            #     "current_price": round(new_price, 2),
            #     "volume": volume,
            #     "percentage_change": percentage_change
            # })
            open_price = prices.get(stock, 100)  # Starting open price is 100.
            volume = random.randint(1000, 10000)
            price_change = random.uniform(-3, 3)
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
            await asyncio.sleep(10)  # Send update every second
    except (ConnectionClosedOK, ConnectionClosedError):
        # Connection was closed properly or due to an error, handle if needed
        pass
def get_next_price(stock, price_change):
    current_price = prices.get(stock, 100)  # Starting price is 100.
    new_price = current_price + price_change
    prices[stock] = new_price
    # print(new_price)
    return round(new_price, 2)

async def main():
    # Start the background task
    print('Server started....')
    # asyncio.create_task(update_prices())

    # Start WebSocket server and handle paths
    # async with websockets.serve(produce_mock_data, 'localhost', 8765):
    async with websockets.serve(produce_mock_data, 'ec2-16-16-77-63.eu-north-1.compute.amazonaws.com', 8765):
        await asyncio.Future()  # Run forever
    print('Running....')

# Run the server
asyncio.run(main())
