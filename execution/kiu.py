import pandas as pd

# Assuming you have a DataFrame 'df' with columns 'datetime', 'symbol', and 'close'
# 'datetime' should be in datetime format, 'symbol' is the asset identifier, 'close' is the closing price

# Sample DataFrame creation (replace this with your actual data loading)
data = {
    'datetime': ['2024-01-19', '2024-01-20', '2024-01-21', '2024-01-22', '2024-01-23'],
    'symbol': ['AAPL', 'AAPL', 'AAPL', 'AAPL', 'AAPL'],
    'close': [150.0, 155.0, 152.0, 158.0, 160.0]
}

df = pd.DataFrame(data)
df['datetime'] = pd.to_datetime(df['datetime'])

# Sort DataFrame by 'datetime' and 'symbol' for proper calculation
df = df.sort_values(by=['symbol', 'datetime'])

# Calculate daily returns using pct_change()
df['daily_return'] = df.groupby('symbol')['close'].pct_change()

# Print the DataFrame with daily returns
print(df)
