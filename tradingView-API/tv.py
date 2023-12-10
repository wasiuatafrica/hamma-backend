from tvDatafeed import TvDatafeed, Interval

# from .tradingView import search
username = 'YourTradingViewUsername'
password = 'YourTradingViewPassword'

# tv = TvDatafeed(username, password)
tv = TvDatafeed()

data = tv.get_hist(symbol='ZENITHBANK',exchange='NSENG',interval=Interval.in_1_hour,n_bars=1000000000)
print(data.head())
print(data.tail())

# data = search('ZENITHBANK', 'stock')
# print(data)