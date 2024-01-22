from tvDatafeed import TvDatafeed, Interval

# from .tradingView import search
# username = 'YourTradingViewUsername'
# password = 'YourTradingViewPassword'

# # tv = TvDatafeed(username, password)
tv = TvDatafeed()

# data = tv.get_hist(symbol='ZENITHBANK',exchange='NSENG',interval=Interval.in_1_hour ,n_bars=2)
# # print(data.head())
# # print(data.tail())
# print(data[-1])

# # data = search('ZENITHBANK', 'stock')
# # print(data)


# def get_last_data_dict(data):
#     # Reset the index to convert the datetime index to a column
#     data_reset = data.reset_index()

#     # Get the last row as a dictionary
#     last_data_dict = data_reset.iloc[-2].to_dict()
#     last_data_dict['datetime'] = last_data_dict['datetime'].strftime('%Y-%m-%d %H:%M:%S')


#     return last_data_dict

# # Example usage:
# # Assuming data is your Pandas DataFrame
# data = tv.get_hist(symbol='ZENITHBANK', exchange='NSENG', interval=Interval.in_1_minute, n_bars=2)

def get_data(symbol):
    data = tv.get_hist(symbol=symbol, exchange='NSENG', interval=Interval.in_1_minute, n_bars=2)

    # Check if data is None before processing
    if data is not None and not data.empty:
        data_reset = data.reset_index()

        # Convert the last two rows to dictionaries
        last_data_dicts = [row.to_dict() for _, row in data_reset.iloc[-2:].iterrows()]

        # Format the 'datetime' field as a string
        for entry in last_data_dicts:
            entry['datetime'] = entry['datetime'].strftime('%Y-%m-%d %H:%M:%S')

        return last_data_dicts
    else:
        print(f"No data available for symbol: {symbol}")
        return None

last_data_dict = get_data("ZENITHBANK")

# Print the dictionary
print(last_data_dict)