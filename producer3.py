import asyncio
import json
import random
import websockets
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

# List of stocks
stocks = [
    # ... as before
]

# Dictionary to keep track of current prices
prices = {stock: 100.0 for stock in stocks}

# Authentication token
AUTH_TOKEN = "Ab$455"

async def produce_mock_data(websocket, path):
    print('Client connected, waiting for authentication...')
    try:
        # Authentication
        auth_token = await websocket.recv()
        if auth_token != AUTH_TOKEN:
            await websocket.close(code=1008, reason="Invalid token")
            return
    except websockets.exceptions.ConnectionClosed:
        return

    # Initialize the subscription set for this connection
    subscribed_stocks = set()

    try:
        # Main event loop for the connection
        while True:
            try:
                # Listen for subscribe/unsubscribe messages
                message = await asyncio.wait_for(websocket.recv(), timeout=1)
                command = json.loads(message)

                if "action" in command and "symbols" in command:
                    if command["action"] == "subscribe":
                        for symbol in command["symbols"]:
                            if symbol in stocks:
                                subscribed_stocks.add(symbol)
                    elif command["action"] == "unsubscribe":
                        for symbol in command["symbols"]:
                            subscribed_stocks.discard(symbol)
                else:
                    print("Received invalid message from client:", message)
            except asyncio.TimeoutError:
                # No message received, continue with sending updates
                pass

            # Broadcast updates for all subscribed stocks
            for stock in subscribed_stocks:
                open_price = prices.get(stock, 100)
                volume = random.randint(1000, 10000)
                price_change = random.uniform(-3, 3)
                new_price = get_next_price(stock, price_change)
                percentage_change = ((new_price - open_price) / open_price) * 100

                update = json.dumps({
                    "stock": stock,
                    "open_price": round(open_price, 2),
                    "current_price": round(new_price, 2),
                    "volume": volume,
                    "percentage_change": round(percentage_change, 2)
                })
                await websocket.send(update)
            await asyncio.sleep(1)  # Send update every second
    except (ConnectionClosedOK, ConnectionClosedError):
        # Connection was closed properly or due to an error, handle if needed
        print('Client disconnected')
    except json.JSONDecodeError:
        # Received non-JSON message from the client
        await websocket.close(code=1008, reason="Invalid message format")

def get_next_price(stock, price_change):
    # ... as before

async def main():
    # ... as before

# Run the server
asyncio.run(main())
