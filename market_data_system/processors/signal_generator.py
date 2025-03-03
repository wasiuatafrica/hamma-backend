import requests
import json
import time
from datetime import datetime

from common.utils.config import settings
from common.logging.logger import get_logger
from common.db.mongodb import mongodb
from common.db.postgres import postgres_db
from notifications.alert_manager import alert_manager
from common.utils.market_utils import is_market_open, get_current_time_lagos

logger = get_logger(__name__)


class SignalGenerator:
    def __init__(self):
        self.db = mongodb

    def get_signal_1hr(self, symbol):
        """Get 1-hour indicator signals from TradingView."""
        try:
            url = f"https://scanner.tradingview.com/symbol?symbol=NSENG:{symbol}&fields=Recommend.Other|60,Recommend.All|60,Recommend.MA|60,RSI|60,RSI[1]|60,Stoch.K|60,Stoch.D|60,Stoch.K[1]|60,Stoch.D[1]|60,CCI20|60,CCI20[1]|60,ADX|60,ADX+DI|60,ADX-DI|60,ADX+DI[1]|60,ADX-DI[1]|60,AO|60,AO[1]|60,AO[2]|60,Mom|60,Mom[1]|60,MACD.macd|60,MACD.signal|60,Rec.Stoch.RSI|60,Stoch.RSI.K|60,Rec.WR|60,W.R|60,Rec.BBPower|60,BBPower|60,Rec.UO|60,UO|60,EMA10|60,close|60,SMA10|60,EMA20|60,SMA20|60,EMA30|60,SMA30|60,EMA50|60,SMA50|60,EMA100|60,SMA100|60,EMA200|60,SMA200|60,Rec.Ichimoku|60,Ichimoku.BLine|60,Rec.VWMA|60,VWMA|60,Rec.HullMA9|60,HullMA9|60,Pivot.M.Classic.S3|60,Pivot.M.Classic.S2|60,Pivot.M.Classic.S1|60,Pivot.M.Classic.Middle|60,Pivot.M.Classic.R1|60,Pivot.M.Classic.R2|60,Pivot.M.Classic.R3|60,Pivot.M.Fibonacci.S3|60,Pivot.M.Fibonacci.S2|60,Pivot.M.Fibonacci.S1|60,Pivot.M.Fibonacci.Middle|60,Pivot.M.Fibonacci.R1|60,Pivot.M.Fibonacci.R2|60,Pivot.M.Fibonacci.R3|60,Pivot.M.Camarilla.S3|60,Pivot.M.Camarilla.S2|60,Pivot.M.Camarilla.S1|60,Pivot.M.Camarilla.Middle|60,Pivot.M.Camarilla.R1|60,Pivot.M.Camarilla.R2|60,Pivot.M.Camarilla.R3|60,Pivot.M.Woodie.S3|60,Pivot.M.Woodie.S2|60,Pivot.M.Woodie.S1|60,Pivot.M.Woodie.Middle|60,Pivot.M.Woodie.R1|60,Pivot.M.Woodie.R2|60,Pivot.M.Woodie.R3|60,Pivot.M.Demark.S1|60,Pivot.M.Demark.Middle|60,Pivot.M.Demark.R1|60&no_404=true&label-product=popup-technicals"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.json()
            logger.warning(
                f"Failed to get 1hr signals for {symbol}: {response.status_code}"
            )
            return None
        except Exception as e:
            logger.error(f"Error getting 1hr signals for {symbol}: {e}")
            return None

    def get_signal_1dy(self, symbol):
        """Get daily indicator signals from TradingView."""
        try:
            url = f"https://scanner.tradingview.com/symbol?symbol=NSENG:{symbol}&fields=Recommend.Other,Recommend.All,Recommend.MA,RSI,RSI[1],Stoch.K,Stoch.D,Stoch.K[1],Stoch.D[1],CCI20,CCI20[1],ADX,ADX+DI,ADX-DI,ADX+DI[1],ADX-DI[1],AO,AO[1],AO[2],Mom,Mom[1],MACD.macd,MACD.signal,Rec.Stoch.RSI,Stoch.RSI.K,Rec.WR,W.R,Rec.BBPower,BBPower,Rec.UO,UO,EMA10,close,SMA10,EMA20,SMA20,EMA30,SMA30,EMA50,SMA50,EMA100,SMA100,EMA200,SMA200,Rec.Ichimoku,Ichimoku.BLine,Rec.VWMA,VWMA,Rec.HullMA9,HullMA9,Pivot.M.Classic.S3,Pivot.M.Classic.S2,Pivot.M.Classic.S1,Pivot.M.Classic.Middle,Pivot.M.Classic.R1,Pivot.M.Classic.R2,Pivot.M.Classic.R3,Pivot.M.Fibonacci.S3,Pivot.M.Fibonacci.S2,Pivot.M.Fibonacci.S1,Pivot.M.Fibonacci.Middle,Pivot.M.Fibonacci.R1,Pivot.M.Fibonacci.R2,Pivot.M.Fibonacci.R3,Pivot.M.Camarilla.S3,Pivot.M.Camarilla.S2,Pivot.M.Camarilla.S1,Pivot.M.Camarilla.Middle,Pivot.M.Camarilla.R1,Pivot.M.Camarilla.R2,Pivot.M.Camarilla.R3,Pivot.M.Woodie.S3,Pivot.M.Woodie.S2,Pivot.M.Woodie.S1,Pivot.M.Woodie.Middle,Pivot.M.Woodie.R1,Pivot.M.Woodie.R2,Pivot.M.Woodie.R3,Pivot.M.Demark.S1,Pivot.M.Demark.Middle,Pivot.M.Demark.R1&no_404=true&label-product=popup-technicals"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.json()
            logger.warning(
                f"Failed to get daily signals for {symbol}: {response.status_code}"
            )
            return None
        except Exception as e:
            logger.error(f"Error getting daily signals for {symbol}: {e}")
            return None

    def get_signal_1week(self, symbol):
        """Get weekly indicator signals from TradingView."""
        try:
            url = f"https://scanner.tradingview.com/symbol?symbol=NSENG:{symbol}&fields=Recommend.Other|1W,Recommend.All|1W,Recommend.MA|1W,RSI|1W,RSI[1]|1W,Stoch.K|1W,Stoch.D|1W,Stoch.K[1]|1W,Stoch.D[1]|1W,CCI20|1W,CCI20[1]|1W,ADX|1W,ADX+DI|1W,ADX-DI|1W,ADX+DI[1]|1W,ADX-DI[1]|1W,AO|1W,AO[1]|1W,AO[2]|1W,Mom|1W,Mom[1]|1W,MACD.macd|1W,MACD.signal|1W,Rec.Stoch.RSI|1W,Stoch.RSI.K|1W,Rec.WR|1W,W.R|1W,Rec.BBPower|1W,BBPower|1W,Rec.UO|1W,UO|1W,EMA10|1W,close|1W,SMA10|1W,EMA20|1W,SMA20|1W,EMA30|1W,SMA30|1W,EMA50|1W,SMA50|1W,EMA100|1W,SMA100|1W,EMA200|1W,SMA200|1W,Rec.Ichimoku|1W,Ichimoku.BLine|1W,Rec.VWMA|1W,VWMA|1W,Rec.HullMA9|1W,HullMA9|1W,Pivot.M.Classic.S3|1W,Pivot.M.Classic.S2|1W,Pivot.M.Classic.S1|1W,Pivot.M.Classic.Middle|1W,Pivot.M.Classic.R1|1W,Pivot.M.Classic.R2|1W,Pivot.M.Classic.R3|1W,Pivot.M.Fibonacci.S3|1W,Pivot.M.Fibonacci.S2|1W,Pivot.M.Fibonacci.S1|1W,Pivot.M.Fibonacci.Middle|1W,Pivot.M.Fibonacci.R1|1W,Pivot.M.Fibonacci.R2|1W,Pivot.M.Fibonacci.R3|1W,Pivot.M.Camarilla.S3|1W,Pivot.M.Camarilla.S2|1W,Pivot.M.Camarilla.S1|1W,Pivot.M.Camarilla.Middle|1W,Pivot.M.Camarilla.R1|1W,Pivot.M.Camarilla.R2|1W,Pivot.M.Camarilla.R3|1W,Pivot.M.Woodie.S3|1W,Pivot.M.Woodie.S2|1W,Pivot.M.Woodie.S1|1W,Pivot.M.Woodie.Middle|1W,Pivot.M.Woodie.R1|1W,Pivot.M.Woodie.R2|1W,Pivot.M.Woodie.R3|1W,Pivot.M.Demark.S1|1W,Pivot.M.Demark.Middle|1W,Pivot.M.Demark.R1|1W&no_404=true&label-product=popup-technicals"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.json()
            logger.warning(
                f"Failed to get weekly signals for {symbol}: {response.status_code}"
            )
            return None
        except Exception as e:
            logger.error(f"Error getting weekly signals for {symbol}: {e}")
            return None

    def get_signal_1month(self, symbol):
        """Get monthly indicator signals from TradingView."""
        try:
            url = f"https://scanner.tradingview.com/symbol?symbol=NSENG:{symbol}&fields=Recommend.Other|1M,Recommend.All|1M,Recommend.MA|1M,RSI|1M,RSI[1]|1M,Stoch.K|1M,Stoch.D|1M,Stoch.K[1]|1M,Stoch.D[1]|1M,CCI20|1M,CCI20[1]|1M,ADX|1M,ADX+DI|1M,ADX-DI|1M,ADX+DI[1]|1M,ADX-DI[1]|1M,AO|1M,AO[1]|1M,AO[2]|1M,Mom|1M,Mom[1]|1M,MACD.macd|1M,MACD.signal|1M,Rec.Stoch.RSI|1M,Stoch.RSI.K|1M,Rec.WR|1M,W.R|1M,Rec.BBPower|1M,BBPower|1M,Rec.UO|1M,UO|1M,EMA10|1M,close|1M,SMA10|1M,EMA20|1M,SMA20|1M,EMA30|1M,SMA30|1M,EMA50|1M,SMA50|1M,EMA100|1M,SMA100|1M,EMA200|1M,SMA200|1M,Rec.Ichimoku|1M,Ichimoku.BLine|1M,Rec.VWMA|1M,VWMA|1M,Rec.HullMA9|1M,HullMA9|1M,Pivot.M.Classic.S3|1M,Pivot.M.Classic.S2|1M,Pivot.M.Classic.S1|1M,Pivot.M.Classic.Middle|1M,Pivot.M.Classic.R1|1M,Pivot.M.Classic.R2|1M,Pivot.M.Classic.R3|1M,Pivot.M.Fibonacci.S3|1M,Pivot.M.Fibonacci.S2|1M,Pivot.M.Fibonacci.S1|1M,Pivot.M.Fibonacci.Middle|1M,Pivot.M.Fibonacci.R1|1M,Pivot.M.Fibonacci.R2|1M,Pivot.M.Fibonacci.R3|1M,Pivot.M.Camarilla.S3|1M,Pivot.M.Camarilla.S2|1M,Pivot.M.Camarilla.S1|1M,Pivot.M.Camarilla.Middle|1M,Pivot.M.Camarilla.R1|1M,Pivot.M.Camarilla.R2|1M,Pivot.M.Camarilla.R3|1M,Pivot.M.Woodie.S3|1M,Pivot.M.Woodie.S2|1M,Pivot.M.Woodie.S1|1M,Pivot.M.Woodie.Middle|1M,Pivot.M.Woodie.R1|1M,Pivot.M.Woodie.R2|1M,Pivot.M.Woodie.R3|1M,Pivot.M.Demark.S1|1M,Pivot.M.Demark.Middle|1M,Pivot.M.Demark.R1|1M&no_404=true&label-product=popup-technicals"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.json()
            logger.warning(
                f"Failed to get monthly signals for {symbol}: {response.status_code}"
            )
            return None
        except Exception as e:
            logger.error(f"Error getting monthly signals for {symbol}: {e}")
            return None

    def analyze_indicators(
        self, data_1m=None, data_1w=None, data_1d=None, data_1h=None
    ):
        """Analyze indicators for all time periods."""

        def get_period_suffix(period):
            if period == "1M":
                return "|1M"
            if period == "1W":
                return "|1W"
            if period == "1D":
                return ""
            if period == "1H":
                return "|60"
            return ""

        def get_action_rsi(value):
            if value < 30:
                return "Buy"
            elif value > 70:
                return "Sell"
            return "Neutral"

        def get_action_stoch(value):
            if value < 20:
                return "Buy"
            elif value > 80:
                return "Sell"
            return "Neutral"

        def get_action_cci(value):
            if value < -100:
                return "Buy"
            elif value > 100:
                return "Sell"
            return "Neutral"

        def get_action_adx(adx_value, di_plus, di_minus):
            if adx_value > 25:
                if di_plus > di_minus:
                    return "Buy"
                elif di_minus > di_plus:
                    return "Sell"
            return "Neutral"

        def get_action_ao(value):
            return "Buy" if value > 0 else "Sell"

        def get_action_mom(value):
            return "Buy" if value > 0 else "Sell"

        def get_action_macd(macd, signal):
            return "Buy" if macd > signal else "Sell"

        def get_action_wr(value):
            if value < -80:
                return "Buy"
            elif value > -20:
                return "Sell"
            return "Neutral"

        def get_action_uo(value):
            if value < 30:
                return "Buy"
            elif value > 70:
                return "Sell"
            return "Neutral"

        def get_action_ma(price, ma_value):
            return "Buy" if price > ma_value else "Sell"

        def analyze_single_period(data, period):
            if not data:
                return {}

            suffix = get_period_suffix(period)
            oscillators = {}
            moving_averages = {}

            # RSI
            rsi_key = f"RSI{suffix}"
            if rsi_key in data:
                rsi_value = data.get(rsi_key, "-")
                action = (
                    get_action_rsi(rsi_value)
                    if isinstance(rsi_value, (int, float))
                    else "-"
                )
                oscillators["Relative Strength Index (14)"] = {
                    "value": (
                        round(rsi_value, 2)
                        if isinstance(rsi_value, (int, float))
                        else "-"
                    ),
                    "action": action,
                }

            # Stochastic
            stoch_k = f"Stoch.K{suffix}"
            if stoch_k in data:
                stoch_value = data.get(stoch_k, "-")
                action = (
                    get_action_stoch(stoch_value)
                    if isinstance(stoch_value, (int, float))
                    else "-"
                )
                oscillators["Stochastic %K (14, 3, 3)"] = {
                    "value": (
                        round(stoch_value, 2)
                        if isinstance(stoch_value, (int, float))
                        else "-"
                    ),
                    "action": action,
                }

            # Stochastic RSI Fast
            stoch_rsi_key = f"Stoch.RSI.K{suffix}"
            if stoch_rsi_key in data:
                stoch_rsi_value = data.get(stoch_rsi_key, "-")
                if isinstance(stoch_rsi_value, (int, float)):
                    action = (
                        "Buy"
                        if stoch_rsi_value < 20
                        else "Sell" if stoch_rsi_value > 80 else "Neutral"
                    )
                    oscillators["Stochastic RSI Fast (3, 3, 14, 14)"] = {
                        "value": round(stoch_rsi_value, 2),
                        "action": action,
                    }

            # CCI
            cci_key = f"CCI20{suffix}"
            if cci_key in data:
                cci_value = data.get(cci_key, "-")
                action = (
                    get_action_cci(cci_value)
                    if isinstance(cci_value, (int, float))
                    else "-"
                )
                oscillators["Commodity Channel Index (20)"] = {
                    "value": (
                        round(cci_value, 2)
                        if isinstance(cci_value, (int, float))
                        else "-"
                    ),
                    "action": action,
                }

            # ADX
            adx_key = f"ADX{suffix}"
            di_plus_key = f"ADX+DI{suffix}"
            di_minus_key = f"ADX-DI{suffix}"
            if adx_key in data and di_plus_key in data and di_minus_key in data:
                adx_value = data.get(adx_key, "-")
                di_plus = data.get(di_plus_key, "-")
                di_minus = data.get(di_minus_key, "-")
                action = (
                    get_action_adx(adx_value, di_plus, di_minus)
                    if all(
                        isinstance(x, (int, float))
                        for x in [adx_value, di_plus, di_minus]
                    )
                    else "-"
                )
                oscillators["Average Directional Index (14)"] = {
                    "value": (
                        round(adx_value, 2)
                        if isinstance(adx_value, (int, float))
                        else "-"
                    ),
                    "action": action,
                }

            # Awesome Oscillator
            ao_key = f"AO{suffix}"
            if ao_key in data:
                ao_value = data.get(ao_key, "-")
                action = (
                    get_action_ao(ao_value)
                    if isinstance(ao_value, (int, float))
                    else "-"
                )
                oscillators["Awesome Oscillator"] = {
                    "value": (
                        round(ao_value, 2)
                        if isinstance(ao_value, (int, float))
                        else "-"
                    ),
                    "action": action,
                }

            # Momentum
            mom_key = f"Mom{suffix}"
            if mom_key in data:
                mom_value = data.get(mom_key, "-")
                action = (
                    get_action_mom(mom_value)
                    if isinstance(mom_value, (int, float))
                    else "-"
                )
                oscillators["Momentum (10)"] = {
                    "value": (
                        round(mom_value, 2)
                        if isinstance(mom_value, (int, float))
                        else "-"
                    ),
                    "action": action,
                }

            # MACD
            macd_key = f"MACD.macd{suffix}"
            macd_signal_key = f"MACD.signal{suffix}"
            if macd_key in data and macd_signal_key in data:
                macd_value = data.get(macd_key, "-")
                signal_value = data.get(macd_signal_key, "-")
                action = (
                    get_action_macd(macd_value, signal_value)
                    if all(
                        isinstance(x, (int, float)) for x in [macd_value, signal_value]
                    )
                    else "-"
                )
                oscillators["MACD Level (12, 26)"] = {
                    "value": (
                        round(macd_value, 2)
                        if isinstance(macd_value, (int, float))
                        else "-"
                    ),
                    "action": action,
                }

            # Moving Averages
            price_key = f"close{suffix}"
            if price_key in data:
                price = data.get(price_key, "-")
                for period in [10, 20, 30, 50, 100, 200]:
                    ema_key = f"EMA{period}{suffix}"
                    sma_key = f"SMA{period}{suffix}"

                    if ema_key in data:
                        ema_value = data.get(ema_key, "-")
                        if isinstance(price, (int, float)) and isinstance(
                            ema_value, (int, float)
                        ):
                            action = get_action_ma(price, ema_value)
                            moving_averages[
                                f"Exponential Moving Average ({period})"
                            ] = {
                                "value": round(ema_value, 2),
                                "action": action,
                            }

                    if sma_key in data:
                        sma_value = data.get(sma_key, "-")
                        if isinstance(price, (int, float)) and isinstance(
                            sma_value, (int, float)
                        ):
                            action = get_action_ma(price, sma_value)
                            moving_averages[f"Simple Moving Average ({period})"] = {
                                "value": round(sma_value, 2),
                                "action": action,
                            }

                # VWMA
                vwma_key = f"VWMA{suffix}"
                if vwma_key in data:
                    vwma_value = data.get(vwma_key, "-")
                    if isinstance(vwma_value, (int, float)):
                        action = (
                            "Buy"
                            if price > vwma_value
                            else "Sell" if price < vwma_value else "Neutral"
                        )
                        moving_averages["Volume Weighted Moving Average (20)"] = {
                            "value": round(vwma_value, 2),
                            "action": action,
                        }

                # Ichimoku Base Line
                ichimoku_key = f"Ichimoku.BLine{suffix}"
                if ichimoku_key in data:
                    ichimoku_value = data.get(ichimoku_key, "-")
                    if isinstance(ichimoku_value, (int, float)):
                        action = (
                            "Buy"
                            if price > ichimoku_value
                            else "Sell" if price < ichimoku_value else "Neutral"
                        )
                        moving_averages["Ichimoku Base Line (9, 26, 52, 26)"] = {
                            "value": round(ichimoku_value, 2),
                            "action": action,
                        }

            return {
                "Oscillators": oscillators,
                "MovingAverages": moving_averages,
            }

        periods_data = {"1M": data_1m, "1W": data_1w, "1D": data_1d, "1H": data_1h}

        analysis = {
            period: analyze_single_period(data, period)
            for period, data in periods_data.items()
            if data
        }
        return analysis

    def calculate_oscillator_signals(self, indicators):
        """Calculate signals from oscillators."""
        oscillators = [
            "Relative Strength Index (14)",
            "Stochastic %K (14, 3, 3)",
            "Stochastic RSI Fast (3, 3, 14, 14)",
            "Commodity Channel Index (20)",
            "Awesome Oscillator",
            "Momentum (10)",
            "MACD Level (12, 26)",
            "Williams Percent Range (14)",
            "Bull Bear Power",
            "Ultimate Oscillator (7, 14, 28)",
        ]

        counts = {"Buy": 0, "Sell": 0, "Neutral": 0}

        for ind in oscillators:
            if ind in indicators and indicators[ind]["action"] in counts:
                counts[indicators[ind]["action"]] += 1

        total = sum(counts.values())
        if total == 0:
            total = 1  # Prevent division by zero

        percentages = {
            "Buy": (counts["Buy"] / total) * 100,
            "Sell": (counts["Sell"] / total) * 100,
            "Neutral": (counts["Neutral"] / total) * 100,
        }

        # Determine signal
        if counts["Buy"] > counts["Sell"] and counts["Buy"] > counts["Neutral"]:
            signal = "Strong buy" if counts["Buy"] >= total * 0.7 else "Buy"
        elif counts["Sell"] > counts["Buy"] and counts["Sell"] > counts["Neutral"]:
            signal = "Strong sell" if counts["Sell"] >= total * 0.7 else "Sell"
        else:
            signal = "Neutral"

        return {"counts": counts, "percentages": percentages, "signal": signal}

    def calculate_moving_average_signals(self, indicators):
        """Calculate signals from moving averages."""
        moving_averages = [
            "Exponential Moving Average (10)",
            "Simple Moving Average (10)",
            "Exponential Moving Average (20)",
            "Simple Moving Average (20)",
            "Exponential Moving Average (30)",
            "Simple Moving Average (30)",
            "Exponential Moving Average (50)",
            "Simple Moving Average (50)",
            "Exponential Moving Average (100)",
            "Simple Moving Average (100)",
            "Exponential Moving Average (200)",
            "Simple Moving Average (200)",
            "Volume Weighted Moving Average (20)",
            "Ichimoku Base Line (9, 26, 52, 26)",
            "Hull Moving Average (9)",
        ]

        counts = {"Buy": 0, "Sell": 0, "Neutral": 0}

        for ind in moving_averages:
            if ind in indicators and indicators[ind]["action"] in counts:
                counts[indicators[ind]["action"]] += 1

        total = sum(counts.values())
        if total == 0:
            total = 1  # Prevent division by zero

        percentages = {
            "Buy": (counts["Buy"] / total) * 100,
            "Sell": (counts["Sell"] / total) * 100,
            "Neutral": (counts["Neutral"] / total) * 100,
        }

        # Determine signal
        if counts["Buy"] > counts["Sell"] and counts["Buy"] > counts["Neutral"]:
            signal = "Strong buy" if counts["Buy"] >= total * 0.7 else "Buy"
        elif counts["Sell"] > counts["Buy"] and counts["Sell"] > counts["Neutral"]:
            signal = "Strong sell" if counts["Sell"] >= total * 0.7 else "Sell"
        else:
            signal = "Neutral"

        return {"counts": counts, "percentages": percentages, "signal": signal}

    def calculate_summary_signals(self, oscillator_data, ma_data):
        """Calculate summary signals from oscillators and moving averages."""
        # Combine counts from both analyses
        total_counts = {
            "Buy": oscillator_data["counts"]["Buy"] + ma_data["counts"]["Buy"],
            "Sell": oscillator_data["counts"]["Sell"] + ma_data["counts"]["Sell"],
            "Neutral": oscillator_data["counts"]["Neutral"]
            + ma_data["counts"]["Neutral"],
        }

        total = sum(total_counts.values())

        total_valid = total_counts["Buy"] + total_counts["Sell"]
        if total_valid == 0:
            total_valid = 1  # Prevent division by zero

        percentages = {}
        buy = round(total_counts["Buy"] / total_valid * 100)
        sell = abs(100 - buy)

        percentages["Buy"] = buy
        percentages["Sell"] = sell

        # Determine overall signal
        if (
            total_counts["Buy"] > total_counts["Sell"]
            and total_counts["Buy"] > total_counts["Neutral"]
        ):
            signal = "Strong buy" if total_counts["Buy"] >= total * 0.7 else "Buy"
        elif (
            total_counts["Sell"] > total_counts["Buy"]
            and total_counts["Sell"] > total_counts["Neutral"]
        ):
            signal = "Strong sell" if total_counts["Sell"] >= total * 0.7 else "Sell"
        else:
            signal = "Neutral"

        return {"counts": total_counts, "percentages": percentages, "signal": signal}

    def get_all_signals(self, data):
        """Process all signals from the analyzed data."""
        result = {}

        for period in ["1M", "1W", "1D", "1H"]:
            if period not in data:
                continue

            indicators = data[period]

            oscillator_signals = self.calculate_oscillator_signals(
                indicators["Oscillators"]
            )
            ma_signals = self.calculate_moving_average_signals(
                indicators["MovingAverages"]
            )
            summary_signals = self.calculate_summary_signals(
                oscillator_signals, ma_signals
            )

            result[period] = {
                "oscillators": oscillator_signals,
                "moving_averages": ma_signals,
                "summary": summary_signals,
            }

        return result

    def process_symbol(self, symbol):
        """Process trading signals for a single symbol."""
        try:
            logger.info(f"Processing signals for {symbol}")

            # Get data for each timeframe
            data = {}
            data["1month"] = self.get_signal_1month(symbol)
            data["1week"] = self.get_signal_1week(symbol)
            data["1day"] = self.get_signal_1dy(symbol)
            data["1hour"] = self.get_signal_1hr(symbol)

            # Analyze indicators
            analysis_data = self.analyze_indicators(
                data["1month"],
                data["1week"],
                data["1day"],
                data["1hour"],
            )

            # Get signals
            signal_data = self.get_all_signals(analysis_data)

            # Prepare final data
            final_symbol_data = {"1M": {}, "1W": {}, "1D": {}, "1H": {}}
            for period in ["1M", "1W", "1D", "1H"]:
                if period in analysis_data:
                    final_symbol_data[period]["analysis"] = analysis_data[period]
                if period in signal_data:
                    final_symbol_data[period]["signals"] = signal_data[period]

            final_symbol_data["symbol"] = symbol

            return final_symbol_data
        except Exception as e:
            logger.error(f"Error processing signals for {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}

    def generate_signals(self):
        """Generate trading signals for all active symbols."""
        start_time = time.time()

        try:
            self.db.update_service_status(
                "SignalGenerator", "running", "Generating signals"
            )

            # Get active symbols
            stocks = postgres_db.get_active_stocks()
            symbols = [stock.symbol for stock in stocks]

            collected_data = {}
            failed_symbols = []

            # Process each symbol
            for symbol in symbols:
                try:
                    symbol_data = self.process_symbol(symbol)
                    if symbol_data:
                        collected_data[symbol] = symbol_data
                except Exception as e:
                    logger.error(f"Failed to process signals for {symbol}: {e}")
                    failed_symbols.append(symbol)

            # Save to MongoDB
            if collected_data:
                self.db.db_signals["signals"].insert_one(collected_data)
                logger.info(
                    f"Successfully generated signals for {len(collected_data)} symbols"
                )

            end_time = time.time()
            duration = end_time - start_time

            self.db.record_performance_metric(
                "SignalGenerator", "generate_signals", duration, len(collected_data)
            )

            status_message = f"Generated signals for {len(collected_data)} symbols in {duration:.2f} seconds"
            if failed_symbols:
                status_message += f" ({len(failed_symbols)} symbols failed)"

            self.db.update_service_status(
                "SignalGenerator",
                "success" if not failed_symbols else "partial_success",
                status_message,
            )

            # Send notification
            alert_manager.send_process_completion(
                "Trading Signal Generation",
                f"Generated signals for {len(collected_data)} symbols",
            )

            if failed_symbols:
                alert_manager.handle_error(
                    "SignalGenerator",
                    f"Failed to generate signals for {len(failed_symbols)} symbols",
                    data={"failed_symbols": failed_symbols},
                )

            return collected_data
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time

            error_msg = f"Error generating signals: {str(e)}"
            logger.error(error_msg)

            self.db.update_service_status("SignalGenerator", "error", error_msg)
            alert_manager.handle_error(
                "SignalGenerator", "Failed to generate signals", e
            )

            return None

    def run(self):
        """Run the signal generation process if market is open."""
        if is_market_open():
            logger.info("Market is open, generating trading signals")
            return self.generate_signals()
        else:
            logger.info("Market is closed, skipping signal generation")
            self.db.update_service_status("SignalGenerator", "idle", "Market is closed")
            return None


# Create a singleton instance
signal_generator = SignalGenerator()
