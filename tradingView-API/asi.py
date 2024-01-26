from tvDatafeed import TvDatafeed, Interval
tv = TvDatafeed()

data = tv.get_hist(symbol="ASI", exchange='NSENG', interval=Interval.in_1_hour, n_bars=30)

print(data.head(20))
print(data.tail(20))

data1 = data.reset_index().to_dict(orient='records')
for record in data1:
    record['datetime'] = record['datetime'].strftime('%Y-%m-%d %H:%M:%S')

print(data1)