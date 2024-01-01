import asyncio
import websockets
import json

async def connect_to_websocket(stock_symbol):
    # uri = f"ws://localhost:8765/{stock_symbol}"
    uri = f"ws://ec2-16-16-77-63.eu-north-1.compute.amazonaws.com:8765/{stock_symbol}"

    async with websockets.connect(uri) as websocket:
        try:
            # Sending authentication token
            auth_token = "Ab$455"
            await websocket.send(auth_token)

            while True:
                data = await websocket.recv()
                stock_data = json.loads(data)
                print(stock_data)
                # print(f"Stock: {stock_data['stock']}")
                # print(f"Open Price: {stock_data['open_price']}")
                # print(f"Current Price: {stock_data['current_price']}")
                # print(f"Volume: {stock_data['volume']}")
                # print(f"Percentage Change: {stock_data['percentage_change']}%\n")
        except websockets.exceptions.ConnectionClosed as e:
            if e.code != 1000:
                print(f"Connection closed unexpectedly: {e}")

async def main():
    stock_symbol = "WEMABANK"
    await connect_to_websocket(stock_symbol)

# Run the script
asyncio.run(main())
