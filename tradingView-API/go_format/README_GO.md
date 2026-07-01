# Unified Price System - Go Implementation

This is a Go rewrite of the Python unified price system for trading data collection, processing, and storage.

## Features

- **Real-time data collection** from TradingView API
- **MongoDB integration** for data storage
- **Volatility caching** with 90-minute cache duration
- **Batch operations** for efficient database writes
- **Market hours detection** for Nigerian stock market (10 AM - 2:30 PM WAT)
- **Concurrent processing** with goroutines
- **Comprehensive error handling** and logging
- **Fallback data mechanisms** for reliability

## Architecture

### Core Components

1. **VolatilityCache**: Thread-safe caching system with persistent storage
2. **BatchOperations**: Efficient batch database operations
3. **ChangeDetector**: Detects significant data changes to minimize unnecessary updates
4. **Data Structures**: Type-safe structs for price data, volatility metrics, and merged data

### Data Flow

1. **Live Data Collection**: Fetches real-time price data from TradingView
2. **Volatility Calculation**: Computes volatility and momentum metrics (cached for 90 minutes)
3. **Data Merging**: Combines live prices with volatility metrics
4. **Database Storage**: Saves to MongoDB collections with batch operations

## Installation

1. Ensure Go 1.21+ is installed
2. Set up MongoDB connection
3. Install dependencies:

```bash
cd tradingView-API
go mod download
```

## Configuration

Set the following environment variable:

```bash
export MONGO_URL="your_mongodb_connection_string"
```

## Usage

### Running the System

#### Development Mode
```bash
go run unified_price_system.go
```

#### Production Mode - Build and Run
```bash
# Build the binary
go build -o unified_price_system unified_price_system.go

# Run directly
./unified_price_system

# Run in background (various methods below)
```

#### Running in Background

**Method 1: Using nohup (recommended for simple background execution)**
```bash
nohup ./unified_price_system > system.log 2>&1 &
```

**Method 2: Using screen (allows you to reattach later)**
```bash
# Start a new screen session
screen -S unified_system

# Inside screen, run the application
./unified_price_system

# Detach from screen (Ctrl+A, then D)
# To reattach later: screen -r unified_system
```

**Method 3: Using tmux (similar to screen)**
```bash
# Start a new tmux session
tmux new-session -d -s unified_system './unified_price_system'

# To attach later: tmux attach-session -t unified_system
# To detach: Ctrl+B, then D
```

**Method 4: Using systemd service (recommended for production)**

Create a service file `/etc/systemd/system/unified-price-system.service`:
```ini
[Unit]
Description=Unified Price System
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/devnexx/ATafrica/Anyon-Admin/tradingView-API
Environment=MONGO_URL=your_mongodb_connection_string
ExecStart=/home/devnexx/ATafrica/Anyon-Admin/tradingView-API/unified_price_system
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then manage with systemctl:
```bash
# Enable and start the service
sudo systemctl enable unified-price-system
sudo systemctl start unified-price-system

# Check status
sudo systemctl status unified-price-system

# View logs
sudo journalctl -u unified-price-system -f
```

**Method 5: Using Docker (for containerized deployment)**

Create a `Dockerfile`:
```dockerfile
FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build -o unified_price_system .

FROM alpine:latest
RUN apk --no-cache add ca-certificates tzdata
WORKDIR /root/
COPY --from=builder /app/unified_price_system .
CMD ["./unified_price_system"]
```

Build and run:
```bash
# Build Docker image
docker build -t unified-price-system .

# Run in background
docker run -d \
  --name unified-price-system \
  -e MONGO_URL="your_mongodb_connection_string" \
  --restart unless-stopped \
  unified-price-system
```

#### Process Management

**Check if running:**
```bash
ps aux | grep unified_price_system
```

**Kill the process:**
```bash
# Find the process ID
ps aux | grep unified_price_system

# Kill by PID
kill <PID>

# Or kill by name
pkill -f unified_price_system
```

**Monitor logs:**
```bash
# If using nohup
tail -f system.log

# If using systemd
sudo journalctl -u unified-price-system -f

# If using Docker
docker logs -f unified-price-system
```

### Key Functions

- `runUnifiedSystem()`: Main execution loop
- `mainCycle()`: Single data collection cycle
- `ClearVolatilityCache()`: Clear all cached data
- `GetCacheInfo()`: Get cache statistics
- `ForceCacheRefresh(symbol)`: Force refresh for specific symbol

## Data Collections

### MongoDB Collections

- `stock_prices_trdv.price_combined_trdv`: Volatility and momentum data
- `livelake3.live_price_combined_trdv`: Real-time price data
- `livelake3.merged_live_price_trdv`: Combined live and volatility data
- `portfolio_companyprofile` (PostgreSQL): Shares outstanding and company issuer data per symbol (replaces `ngxlistedcompanies` Mongo)

## Stock Symbols

Supports 150+ Nigerian Stock Exchange (NSE) symbols including:
- Banking: GTCO, ZENITHBANK, UBA, ACCESSCORP, etc.
- Oil & Gas: SEPLAT, OANDO, TOTAL, etc.
- Consumer Goods: DANGSUGAR, NESTLE, UNILEVER, etc.
- Telecommunications: MTNN, AIRTELAFRI, etc.

## Performance Features

### Caching Strategy
- **90-minute cache** for volatility data
- **Automatic cache expiration** and cleanup
- **Persistent cache storage** in JSON format
- **Cache hit rate tracking** for performance monitoring

### Batch Operations
- **Configurable batch size** (default: 50 documents)
- **Auto-flush on batch size** or time interval
- **Concurrent writes** for improved throughput

### Error Handling
- **Retry logic** for TradingView API calls
- **Fallback data** from database when API fails
- **Graceful degradation** during network issues

## Market Hours

- **Trading Days**: Monday to Friday
- **Trading Hours**: 10:00 AM - 2:30 PM West Africa Time (WAT)
- **Auto-detection**: System only runs during market hours
- **Update Interval**: 20 minutes during trading hours

## Monitoring and Logging

The system provides comprehensive logging for:
- Cache performance metrics
- API call success/failure rates
- Database operation status
- Data completeness validation
- Performance statistics

## Differences from Python Version

### Improvements
- **Type Safety**: Strong typing with Go structs
- **Concurrency**: Native goroutines for parallel processing
- **Memory Management**: Better memory efficiency
- **Error Handling**: Explicit error handling with Go's error interface
- **Performance**: Compiled binary for better performance

### Key Changes
- **Thread-safe operations** with mutexes
- **Context-based timeouts** for database operations
- **Structured logging** with standard Go log package
- **JSON-based cache persistence** instead of pickle
- **Native MongoDB driver** with connection pooling

## Development

### Adding New Symbols
Add symbols to the `symbols` slice in the code.

### Extending Metrics
Add new fields to the `VolatilityData` struct and update calculation functions.

### Custom Intervals
Modify the `UpdateInterval` constant for different update frequencies.

## Dependencies

- `go.mongodb.org/mongo-driver`: MongoDB driver for Go
- Standard library packages for JSON, time, context, etc.

## Notes

- The TradingView integration is currently a placeholder - replace with actual API integration
- Market cap calculation uses `shares_outstanding` from PostgreSQL (`portfolio_companyprofile`) or `GET /portfolio/shares-outstanding/` (see `docs/ngxlistedcompanies-postgres.md`)
- Cache files are stored in the same directory as the executable
- The system is designed to be fault-tolerant and can recover from temporary failures

## Future Enhancements

- REST API endpoints for data access
- Metrics dashboard with Prometheus/Grafana
- Real TradingView API integration
- Kubernetes deployment configuration
- Enhanced monitoring and alerting

---

# Original TradingView-API

tradingview socket api for fetching real time prices.

## How to run

```
git clone https://github.com/mohamadkhalaj/tradingView-API.git
cd tradingView-API
pip3 install -r requirements.txt
python3 tradingView.py
```

# How to use

First you should select category type and searching text (by search() function in the code):
```
category list: 'stock' | 'futures' | 'forex' | 'cfd' | 'crypto' | 'index' | 'economic'
```
# Example
```python
data = search('btcusdt', 'crypto')
```

if any results found it will be shown.
