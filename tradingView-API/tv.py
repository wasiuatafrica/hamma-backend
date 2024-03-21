from tvDatafeed import TvDatafeed, Interval

tv = TvDatafeed()


def get_data(symbol):
    data = tv.get_hist(symbol=symbol, exchange='NSENG', interval=Interval.in_daily , n_bars=1)

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