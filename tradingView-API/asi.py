from tvDatafeed import TvDatafeed, Interval
tv = TvDatafeed()

data = tv.get_hist(symbol="ASI", exchange='NSENG', interval=Interval.in_1_minute, n_bars=200)

print(data.head(20))
print(data.tail(20))