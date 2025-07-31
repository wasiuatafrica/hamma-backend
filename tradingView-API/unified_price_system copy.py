import requests
from dotenv import load_dotenv
import os
from tvDatafeed import TvDatafeed, Interval
from pymongo import MongoClient
import pandas as pd
from datetime import datetime, timedelta, time
import time as module_time
import math
import pytz
import numpy as np

# Load environment variables
load_dotenv()

MONGO_URL = os.environ.get("MONGO_URL")
client = MongoClient(MONGO_URL, tls=True, tlsAllowInvalidCertificates=True)

# Database collections
db_stock_prices = client["stock_prices"]
collection_price_combined = db_stock_prices["price_combined"]

db_live = client["livelake3"]
collection_live = db_live["live_price_combined"]
collection_merged = db_live["merged_live_price"]

db_chart = client["chartdata_1D"]
db_cap = client["ngxlistedcompanies"]

# TradingView data feed
tv = TvDatafeed()

# Lagos timezone
lagos_tz = pytz.timezone('Africa/Lagos')

# Stock symbols
symbols = [
    "ABBEYBDS", "ACADEMY", "ACCESSCORP", "AFRIPRUD", "AFRINSURE", "AFROMEDIA",
    "AIICO", "AIRTELAFRI", "ALEX", "ASOSAVINGS", "ABCTRANS", "AUSTINLAZ",
    "MANSARD", "BERGER", "BETAGLAS", "BAPLC", "BUACEMENT", "BUAFOODS",
    "CILEASING", "CADBURY", "CAP", "CAPOIL", "CAVERTON", "CHAMPION",
    "CHAMS", "CHELLARAM", "CONOIL", "CORNERST", "WAPIC", "CUSTODIAN",
    "CUTIX", "CWG", "DAARCOMM", "DANGCEM", "DANGSUGAR", "DEAPCAP",
    "DUNLOP", "ETRANZACT", "ETI", "EKOCORP", "ELLAHLAKES", "ETERNA",
    "EUNISELL", "FBNH", "FCMB", "FIDELITYBK", "FIDSON", "FLOURMILL",
    "FTNCOCOA", "GEREGU", "GOLDBREW", "GOLDINSURE", "VANLEER", "GTCO",
    "GUINEAINS", "GUINNESS", "HONYFLOUR", "IKEJAHOTEL", "IMG", "INFINITY",
    "INTBREW", "INTENEGINS", "JAIZBANK", "JAPAULGOLD", "JOHNHOLT", "JULI",
    "JBERGER", "WAPCO", "LASACO", "LEARNAFRCA", "LINKASSURE", "LIVESTOCK",
    "LIVINGTRUST", "MAYBAKER", "MCNICHOLS", "MEDVIEWAIR", "MEYER", "MORISON",
    "MRS", "MTNN", "MULTITREX", "MULTIVERSE", "MBENEFIT", "NNFM",
    "NASCON", "NCR", "NEIMETH", "NEM", "NESTLE", "NAHCO", "NB",
    "ENAMELWA", "NGXGROUP", "NOTORE", "NPFMCRFBK", "OANDO", "OKOMUOIL",
    "OMATEK", "PZ", "PHARMDEKO", "PREMPAINTS", "PRESCO", "PRESTIGE",
    "RTBRISCOE", "REDSTAREX", "REGALINS", "RONCHESS", "ROYALEX", "SCOA",
    "NSLTECH", "SEPLAT", "SFSREIT", "SKYAVN", "SMURFIT", "SOVRENINS",
    "STACO", "STANBIC", "STDINSURE", "STERLINGNG", "SUNUASSUR", "TANTALIZER",
    "TIP", "THOMASWY", "TOTAL", "TOURIST", "TRANSEXPR", "TRANSCOHOT",
    "TRANSCORP", "TRIPPLEG", "UACN", "UHOMREIT", "UNILEVER", "UBN",
    "UNIONDICON", "UNHOMES", "UBA", "UCAP", "UNITYBNK", "UNIVINSURE",
    "UPL", "UPDC", "UPDCREIT", "VERITASKAP", "VFDGROUP", "VITAFOAM",
    "WEMABANK", "ZENITHBANK"
]


def safe_float(value):
    """
    Returns a safe float value. Converts `inf` and `NaN` to None or a default value.
    """
    if isinstance(value, float):
        if math.isinf(value) or math.isnan(value):
            return None
    return value


def is_market_open():
    """Check if the Nigerian stock market is currently open"""
    lagos_timezone = pytz.timezone("Africa/Lagos")
    current_time_lagos = datetime.now(lagos_timezone).time()

    if datetime.today().weekday() < 5:  # Monday to Friday
        market_open_time = time(10, 2)
        market_close_time = time(14, 42)

        if market_open_time <= current_time_lagos <= market_close_time:
            return True

    return False


def get_live_data_from_tradingview(symbol):
    """Get live data from TradingView for a specific symbol"""
    try:
        data = tv.get_hist(
            symbol=symbol, 
            exchange="NSENG", 
            interval=Interval.in_1_minute, 
            n_bars=2
        )

        if data is not None and not data.empty:
            data_reset = data.reset_index()
            last_two_rows = data_reset.iloc[-2:]
            
            # Get the latest data
            latest_data = last_two_rows.iloc[-1]
            previous_data = last_two_rows.iloc[-2] if len(last_two_rows) > 1 else latest_data
            
            # Calculate change and percentage change
            close_change = latest_data['close'] - previous_data['close']
            percentage_change = (close_change / previous_data['close']) * 100 if previous_data['close'] != 0 else 0

            lagos_now = datetime.now(lagos_tz)
            
            return {
                'datetime': lagos_now.strftime("%Y-%m-%d %H:%M:%S"),
                'open': float(latest_data['open']),
                'high': float(latest_data['high']),
                'low': float(latest_data['low']),
                'close': float(latest_data['close']),
                'volume': int(latest_data['volume']) if not pd.isna(latest_data['volume']) else 0,
                'symbol': symbol,
                'change': round(float(close_change), 2),
                'percent': round(float(percentage_change), 2)
            }
    except Exception as e:
        print(f"Error getting live data for {symbol}: {e}")
        return None


def get_all_live_data():
    """Get live data for all symbols from TradingView"""
    combined = {}
    
    for symbol in symbols:
        print(f"Fetching live data for {symbol}")
        data = get_live_data_from_tradingview(symbol)
        if data:
            combined[symbol] = data
    
    return combined


def get_symbol_cap(symbol):
    """Get market cap data for a symbol"""
    try:
        collection = db_cap[symbol]
        data = collection.find_one()
        return data["SharesOutstanding"] if data else 0
    except:
        return 0


def get_chart_data(symbol):
    """Get chart data for volatility and momentum calculations"""
    try:
        if symbol != "ASI":
            collection = db_chart[symbol]
            symbol_data = collection.find_one(sort=[("_id", -1)])
            if symbol_data:
                symbol_data.pop("_id", None)
                data_df = process_chart_data(symbol_data, symbol)
                return data_df
    except Exception as e:
        print(f"Error getting chart data for {symbol}: {e}")
    return None


def process_chart_data(data, symbol):
    """Process chart data to create DataFrame"""
    try:
        # Create DataFrame from the last 31 items
        df = pd.DataFrame({
            "datetime": [datetime.fromtimestamp(ts) for ts in data["t"][-31:]],
            "open": data["o"][-31:],
            "high": data["h"][-31:],
            "low": data["l"][-31:],
            "close": data["c"][-31:],
            "volume": data["v"][-31:],
        })

        # Calculate change and percentage change
        df["change"] = df["close"] - df["close"].shift(1)
        df["percentage_change"] = (df["change"] / df["close"].shift(1)) * 100

        df.dropna(inplace=True)
        df.set_index("datetime", inplace=True)

        # Add current live data
        live_data = get_live_data_from_tradingview(symbol)
        if live_data:
            new_row = {
                "datetime": pd.to_datetime(live_data["datetime"]),
                "open": live_data["open"],
                "high": live_data["high"],
                "low": live_data["low"],
                "close": live_data["close"],
                "volume": live_data["volume"],
                "change": live_data["change"],
                "percentage_change": live_data["percent"],
            }

            df = pd.concat([df, pd.DataFrame([new_row]).set_index("datetime")])

        return df
    except Exception as e:
        print(f"Error processing chart data for {symbol}: {e}")
        return None


def calculate_volatility_momentum_24hr(symbol, data):
    """Calculate 24-hour volatility and momentum"""
    try:
        if data is None or data.empty:
            return None, None, None, None, None

        df = data.tail(3).copy()
        df = df.dropna(subset=["open", "close"])

        if len(df) < 2:
            return None, None, None, None, None

        df["returns"] = df["close"].pct_change()
        volatility = df["returns"].std() * np.sqrt(252 / 2)

        start_price = df["close"].iloc[-2]
        end_price = df["close"].iloc[-1]
        momentum_change = end_price - start_price
        momentum = (momentum_change / start_price) * 100

        start_volume = df["volume"].iloc[-2]
        end_volume = df["volume"].iloc[-1]
        volume_momentum_change = end_volume - start_volume

        if start_volume == 0:
            volume_momentum = 0
        else:
            volume_momentum = (volume_momentum_change / start_volume) * 100

        return (
            round(volatility, 2),
            round(momentum, 2),
            round(momentum_change, 2),
            round(volume_momentum, 2),
            round(volume_momentum_change, 2),
        )
    except Exception as e:
        print(f"Error calculating 24hr volatility/momentum for {symbol}: {e}")
        return None, None, None, None, None


def calculate_volatility_momentum(data, period):
    """Calculate volatility and momentum for different periods"""
    try:
        if data is None or data.empty:
            return None, None, None, None, None

        data = data.copy()
        now = datetime.now()
        data["datetime"] = pd.to_datetime(data.index)

        if period in [30, 7]:
            filtered_data = data.tail(period).copy()
        else:
            filtered_data = data[data["datetime"] >= (now - timedelta(days=period))].copy()

        if len(filtered_data) < 3:
            return None, None, None, None, None

        # Handle NaN values
        filtered_data = filtered_data.fillna(method="ffill").fillna(method="bfill")

        # Calculate returns
        filtered_data["returns"] = filtered_data["close"].pct_change()
        filtered_data["returns"] = filtered_data["returns"].fillna(0)

        # Calculate annualized volatility
        volatility = filtered_data["returns"].std() * np.sqrt(252 / period)

        start_price = filtered_data["close"].iloc[0]
        end_price = filtered_data["close"].iloc[-1]
        momentum_change = end_price - start_price
        momentum = momentum_change / start_price * 100

        start_volume = filtered_data["volume"].iloc[0]
        end_volume = filtered_data["volume"].iloc[-1]
        volume_momentum_change = end_volume - start_volume

        if start_volume == 0:
            volume_momentum = 0
        else:
            volume_momentum = (volume_momentum_change / start_volume) * 100

        return (
            round(volatility, 2),
            round(momentum, 2),
            round(momentum_change, 2),
            round(volume_momentum, 2),
            round(volume_momentum_change, 2),
        )
    except Exception as e:
        print(f"Error calculating volatility/momentum: {e}")
        return None, None, None, None, None


def calculate_comprehensive_metrics(symbol):
    """Calculate all volatility and momentum metrics for a symbol"""
    data_metrics = {"symbol": symbol}
    
    try:
        # Get daily data for long-term calculations
        data_full = tv.get_hist(
            symbol=symbol,
            exchange="NSENG",
            interval=Interval.in_daily,
            n_bars=365,
        )
        
        if data_full is not None and not data_full.empty:
            # 1-year calculations
            vol_mom_1year = calculate_volatility_momentum(data_full, 365)
            data_metrics["volatility_1year"] = vol_mom_1year[0] if vol_mom_1year else None
            data_metrics["momentum_1year"] = vol_mom_1year[1] if vol_mom_1year else None
            data_metrics["momentum_change_1year"] = vol_mom_1year[2] if vol_mom_1year else None
            data_metrics["volume_momentum_1year"] = vol_mom_1year[3] if vol_mom_1year else None
            data_metrics["volume_momentum_change_1year"] = vol_mom_1year[4] if vol_mom_1year else None

            # Year-to-date calculations
            current_year = datetime.now().year
            data_ytd = data_full[data_full.index.year == current_year]
            vol_mom_ytd = calculate_volatility_momentum(data_ytd, len(data_ytd))
            data_metrics["volatility_ytd"] = vol_mom_ytd[0] if vol_mom_ytd else None
            data_metrics["momentum_ytd"] = vol_mom_ytd[1] if vol_mom_ytd else None
            data_metrics["momentum_change_ytd"] = vol_mom_ytd[2] if vol_mom_ytd else None
            data_metrics["volume_momentum_ytd"] = vol_mom_ytd[3] if vol_mom_ytd else None
            data_metrics["volume_momentum_change_ytd"] = vol_mom_ytd[4] if vol_mom_ytd else None
        else:
            # Set defaults if no data available
            for metric in ["volatility_1year", "momentum_1year", "momentum_change_1year", 
                          "volume_momentum_1year", "volume_momentum_change_1year",
                          "volatility_ytd", "momentum_ytd", "momentum_change_ytd",
                          "volume_momentum_ytd", "volume_momentum_change_ytd"]:
                data_metrics[metric] = None

        # Get chart data for shorter-term calculations
        chart_data = get_chart_data(symbol)
        if chart_data is not None:
            # 1-week calculations
            vol_mom_1week = calculate_volatility_momentum(chart_data, 7)
            data_metrics["volatility_1week"] = vol_mom_1week[0] if vol_mom_1week else None
            data_metrics["momentum_1week"] = vol_mom_1week[1] if vol_mom_1week else None
            data_metrics["momentum_change_1week"] = vol_mom_1week[2] if vol_mom_1week else None
            data_metrics["volume_momentum_1week"] = vol_mom_1week[3] if vol_mom_1week else None
            data_metrics["volume_momentum_change_1week"] = vol_mom_1week[4] if vol_mom_1week else None

            # 1-month calculations
            vol_mom_1month = calculate_volatility_momentum(chart_data, 30)
            data_metrics["volatility"] = vol_mom_1month[0] if vol_mom_1month else None
            data_metrics["momentum"] = vol_mom_1month[1] if vol_mom_1month else None
            data_metrics["momentum_change"] = vol_mom_1month[2] if vol_mom_1month else None
            data_metrics["volume_momentum"] = vol_mom_1month[3] if vol_mom_1month else None
            data_metrics["volume_momentum_change"] = vol_mom_1month[4] if vol_mom_1month else None

            # 24-hour calculations
            vol_mom_24hr = calculate_volatility_momentum_24hr(symbol, chart_data)
            data_metrics["volatility_24hr"] = vol_mom_24hr[0] if vol_mom_24hr else None
            data_metrics["momentum_24hr"] = vol_mom_24hr[1] if vol_mom_24hr else None
            data_metrics["momentum_change_24hr"] = vol_mom_24hr[2] if vol_mom_24hr else None
            data_metrics["volume_momentum_24hr"] = vol_mom_24hr[3] if vol_mom_24hr else None
            data_metrics["volume_momentum_change_24hr"] = vol_mom_24hr[4] if vol_mom_24hr else None

            # Current price
            data_metrics["current_price"] = chart_data.iloc[-1]["close"] if not chart_data.empty else 0
        else:
            # Set defaults if no chart data
            for metric in ["volatility_1week", "momentum_1week", "momentum_change_1week",
                          "volume_momentum_1week", "volume_momentum_change_1week",
                          "volatility", "momentum", "momentum_change",
                          "volume_momentum", "volume_momentum_change",
                          "volatility_24hr", "momentum_24hr", "momentum_change_24hr",
                          "volume_momentum_24hr", "volume_momentum_change_24hr"]:
                data_metrics[metric] = None
            data_metrics["current_price"] = 0

        # Market cap calculation
        try:
            data_metrics["market_cap"] = get_symbol_cap(symbol) * data_metrics["current_price"]
        except:
            data_metrics["market_cap"] = 0

        return data_metrics

    except Exception as e:
        print(f"Error calculating comprehensive metrics for {symbol}: {e}")
        return None


def create_merged_data(live_data, volatility_data):
    """Create merged data combining live prices with volatility metrics"""
    combined = {}
    
    for symbol, live_info in live_data.items():
        if symbol in volatility_data:
            vol_data = volatility_data[symbol]
            
            merged_data = {
                "datetime": live_info["datetime"],
                "symbol": symbol,
                "open": live_info["open"],
                "high": live_info["high"],
                "low": live_info["low"],
                "close": live_info["close"],
                "volume": live_info["volume"],
                "change": live_info["change"],
                "percentage_change": live_info["percent"],
                "current_price": live_info["close"],
                "volatility": safe_float(vol_data.get("volatility")),
                "momentum": safe_float(vol_data.get("momentum")),
                "momentum_change": safe_float(vol_data.get("momentum_change")),
                "volume_momentum": safe_float(vol_data.get("volume_momentum")),
                "volume_momentum_change": safe_float(vol_data.get("volume_momentum_change")),
                "volatility_1week": safe_float(vol_data.get("volatility_1week")),
                "momentum_1week": safe_float(vol_data.get("momentum_1week")),
                "momentum_change_1week": safe_float(vol_data.get("momentum_change_1week")),
                "volume_momentum_1week": safe_float(vol_data.get("volume_momentum_1week")),
                "volume_momentum_change_1week": safe_float(vol_data.get("volume_momentum_change_1week")),
                "volatility_1year": safe_float(vol_data.get("volatility_1year")),
                "momentum_1year": safe_float(vol_data.get("momentum_1year")),
                "momentum_change_1year": safe_float(vol_data.get("momentum_change_1year")),
                "volume_momentum_1year": safe_float(vol_data.get("volume_momentum_1year")),
                "volume_momentum_change_1year": safe_float(vol_data.get("volume_momentum_change_1year")),
                "volatility_ytd": safe_float(vol_data.get("volatility_ytd")),
                "momentum_ytd": safe_float(vol_data.get("momentum_ytd")),
                "momentum_change_ytd": safe_float(vol_data.get("momentum_change_ytd")),
                "volume_momentum_ytd": safe_float(vol_data.get("volume_momentum_ytd")),
                "volume_momentum_change_ytd": safe_float(vol_data.get("volume_momentum_change_ytd")),
                "volatility_24hr": safe_float(vol_data.get("volatility_24hr")),
                "momentum_24hr": safe_float(vol_data.get("momentum_24hr")),
                "momentum_change_24hr": safe_float(vol_data.get("momentum_change_24hr")),
                "volume_momentum_24hr": safe_float(vol_data.get("volume_momentum_24hr")),
                "volume_momentum_change_24hr": safe_float(vol_data.get("volume_momentum_change_24hr")),
                "market_cap": safe_float(vol_data.get("market_cap", 0)),
            }
        else:
            # If no volatility data, use defaults
            merged_data = {
                "datetime": live_info["datetime"],
                "symbol": symbol,
                "open": live_info["open"],
                "high": live_info["high"],
                "low": live_info["low"],
                "close": live_info["close"],
                "volume": live_info["volume"],
                "change": live_info["change"],
                "percentage_change": live_info["percent"],
                "current_price": live_info["close"],
                "volatility": 0,
                "momentum": 0,
                "momentum_change": 0,
                "volume_momentum": 0,
                "volume_momentum_change": 0,
                "volatility_1week": 0,
                "momentum_1week": 0,
                "momentum_change_1week": 0,
                "volume_momentum_1week": 0,
                "volume_momentum_change_1week": 0,
                "volatility_1year": 0,
                "momentum_1year": 0,
                "momentum_change_1year": 0,
                "volume_momentum_1year": 0,
                "volume_momentum_change_1year": 0,
                "volatility_ytd": 0,
                "momentum_ytd": 0,
                "momentum_change_ytd": 0,
                "volume_momentum_ytd": 0,
                "volume_momentum_change_ytd": 0,
                "volatility_24hr": 0,
                "momentum_24hr": 0,
                "momentum_change_24hr": 0,
                "volume_momentum_24hr": 0,
                "volume_momentum_change_24hr": 0,
                "market_cap": 0,
            }
        
        combined[symbol] = merged_data
    
    return combined


def save_data(live_data, volatility_data, merged_data):
    """Save all data to respective MongoDB collections"""
    try:
        # Save live data
        if live_data:
            collection_live.insert_one(live_data)
            # Also save to today's collection
            today_str = datetime.now().strftime("%Y-%m-%d")
            collection_today = db_live[today_str]
            collection_today.insert_one(live_data)
            print("Live data saved")

        # Save volatility data
        if volatility_data:
            collection_price_combined.insert_one(volatility_data)
            print("Volatility data saved")

        # Save merged data
        if merged_data:
            collection_merged.insert_one(merged_data)
            print("Merged data saved")

    except Exception as e:
        print(f"Error saving data: {e}")


def main_cycle():
    """Main execution cycle"""
    if not is_market_open():
        print("Market closed")
        return

    print("Market is open - Starting data collection")
    
    # Step 1: Get live data for all symbols
    print("Step 1: Fetching live data from TradingView...")
    live_data = get_all_live_data()
    
    if not live_data:
        print("No live data retrieved")
        return

    # Step 2: Calculate volatility metrics (less frequent)
    print("Step 2: Calculating volatility and momentum metrics...")
    volatility_data = {}
    for symbol in symbols:
        print(f"Calculating metrics for {symbol}")
        metrics = calculate_comprehensive_metrics(symbol)
        if metrics:
            volatility_data[symbol] = metrics

    # Step 3: Create merged data
    print("Step 3: Merging data...")
    merged_data = create_merged_data(live_data, volatility_data)

    # Step 4: Save all data
    print("Step 4: Saving data...")
    save_data(live_data, volatility_data, merged_data)

    print("Data cycle completed successfully")


def run_unified_system():
    """Run the unified price system"""
    print("Starting Unified Price System")
    print("Using TradingView as primary data source")
    
    # Different update frequencies
    live_update_interval = 60  # 1 minute for live data
    volatility_update_interval = 3600  # 1 hour for volatility calculations
    
    last_volatility_update = 0
    
    while True:
        try:
            current_time = module_time.time()
            today = datetime.today().weekday()
            
            if is_market_open() and today < 5:
                # Always update live data
                live_data = get_all_live_data()
                
                # Update volatility data less frequently
                if current_time - last_volatility_update >= volatility_update_interval:
                    print("Full update cycle (including volatility metrics)")
                    main_cycle()
                    last_volatility_update = current_time
                else:
                    # Quick update - just live data and merge with existing volatility data
                    print("Quick update cycle (live data only)")
                    if live_data:
                        # Get latest volatility data from database
                        latest_volatility = collection_price_combined.find_one(sort=[("_id", -1)])
                        if latest_volatility:
                            latest_volatility.pop("_id", None)
                            merged_data = create_merged_data(live_data, latest_volatility)
                            
                            # Save live and merged data
                            collection_live.insert_one(live_data)
                            today_str = datetime.now().strftime("%Y-%m-%d")
                            collection_today = db_live[today_str]
                            collection_today.insert_one(live_data)
                            collection_merged.insert_one(merged_data)
                            
                            print("Quick update completed")
                
                lagos_now = datetime.now(lagos_tz)
                print(f"Next update in {live_update_interval} seconds - {lagos_now.strftime('%Y-%m-%d %H:%M:%S')}")
                
            else:
                print("Market closed")
            
            module_time.sleep(live_update_interval)
            
        except KeyboardInterrupt:
            print("System stopped by user")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            module_time.sleep(60)  # Wait 1 minute before retrying


if __name__ == "__main__":
    run_unified_system()
