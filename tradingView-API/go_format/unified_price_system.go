package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"os"
	"sync"
	"time"

	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/bson/primitive"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

// Constants
const (
	VolatilityCacheDuration = 90 * time.Minute // 90 minutes
	BatchSize               = 50
	FlushInterval           = 30 * time.Second
	UpdateInterval          = 20 * time.Minute // 20 minutes
	CacheFileName           = "volatility_cache.json"
)

// Data structures
type PriceData struct {
	DateTime   string  `json:"datetime" bson:"datetime"`
	Open       float64 `json:"open" bson:"open"`
	High       float64 `json:"high" bson:"high"`
	Low        float64 `json:"low" bson:"low"`
	Close      float64 `json:"close" bson:"close"`
	Volume     int64   `json:"volume" bson:"volume"`
	Symbol     string  `json:"symbol" bson:"symbol"`
	Change     float64 `json:"change" bson:"change"`
	Percent    float64 `json:"percent" bson:"percent"`
	IsFallback bool    `json:"is_fallback,omitempty" bson:"is_fallback,omitempty"`
}

type VolatilityData struct {
	Symbol                         string    `json:"symbol" bson:"symbol"`
	CurrentPrice                   float64   `json:"current_price" bson:"current_price"`
	Volatility                     *float64  `json:"volatility" bson:"volatility"`
	Momentum                       *float64  `json:"momentum" bson:"momentum"`
	MomentumChange                 *float64  `json:"momentum_change" bson:"momentum_change"`
	VolumeMomentum                 *float64  `json:"volume_momentum" bson:"volume_momentum"`
	VolumeMomentumChange           *float64  `json:"volume_momentum_change" bson:"volume_momentum_change"`
	Volatility1Week                *float64  `json:"volatility_1week" bson:"volatility_1week"`
	Momentum1Week                  *float64  `json:"momentum_1week" bson:"momentum_1week"`
	MomentumChange1Week            *float64  `json:"momentum_change_1week" bson:"momentum_change_1week"`
	VolumeMomentum1Week            *float64  `json:"volume_momentum_1week" bson:"volume_momentum_1week"`
	VolumeMomentumChange1Week      *float64  `json:"volume_momentum_change_1week" bson:"volume_momentum_change_1week"`
	Volatility1Year                *float64  `json:"volatility_1year" bson:"volatility_1year"`
	Momentum1Year                  *float64  `json:"momentum_1year" bson:"momentum_1year"`
	MomentumChange1Year            *float64  `json:"momentum_change_1year" bson:"momentum_change_1year"`
	VolumeMomentum1Year            *float64  `json:"volume_momentum_1year" bson:"volume_momentum_1year"`
	VolumeMomentumChange1Year      *float64  `json:"volume_momentum_change_1year" bson:"volume_momentum_change_1year"`
	VolatilityYTD                  *float64  `json:"volatility_ytd" bson:"volatility_ytd"`
	MomentumYTD                    *float64  `json:"momentum_ytd" bson:"momentum_ytd"`
	MomentumChangeYTD              *float64  `json:"momentum_change_ytd" bson:"momentum_change_ytd"`
	VolumeMomentumYTD              *float64  `json:"volume_momentum_ytd" bson:"volume_momentum_ytd"`
	VolumeMomentumChangeYTD        *float64  `json:"volume_momentum_change_ytd" bson:"volume_momentum_change_ytd"`
	Volatility24Hr                 *float64  `json:"volatility_24hr" bson:"volatility_24hr"`
	Momentum24Hr                   *float64  `json:"momentum_24hr" bson:"momentum_24hr"`
	MomentumChange24Hr             *float64  `json:"momentum_change_24hr" bson:"momentum_change_24hr"`
	VolumeMomentum24Hr             *float64  `json:"volume_momentum_24hr" bson:"volume_momentum_24hr"`
	VolumeMomentumChange24Hr       *float64  `json:"volume_momentum_change_24hr" bson:"volume_momentum_change_24hr"`
	MarketCap                      float64   `json:"market_cap" bson:"market_cap"`
	IsFallback                     bool      `json:"is_fallback,omitempty" bson:"is_fallback,omitempty"`
	Timestamp                      time.Time `json:"timestamp" bson:"timestamp"`
}

type MergedData struct {
	DateTime                       string   `json:"datetime" bson:"datetime"`
	Symbol                         string   `json:"symbol" bson:"symbol"`
	Open                           float64  `json:"open" bson:"open"`
	High                           float64  `json:"high" bson:"high"`
	Low                            float64  `json:"low" bson:"low"`
	Close                          float64  `json:"close" bson:"close"`
	Volume                         int64    `json:"volume" bson:"volume"`
	Change                         float64  `json:"change" bson:"change"`
	PercentageChange               float64  `json:"percentage_change" bson:"percentage_change"`
	CurrentPrice                   float64  `json:"current_price" bson:"current_price"`
	Volatility                     *float64 `json:"volatility" bson:"volatility"`
	Momentum                       *float64 `json:"momentum" bson:"momentum"`
	MomentumChange                 *float64 `json:"momentum_change" bson:"momentum_change"`
	VolumeMomentum                 *float64 `json:"volume_momentum" bson:"volume_momentum"`
	VolumeMomentumChange           *float64 `json:"volume_momentum_change" bson:"volume_momentum_change"`
	Volatility1Week                *float64 `json:"volatility_1week" bson:"volatility_1week"`
	Momentum1Week                  *float64 `json:"momentum_1week" bson:"momentum_1week"`
	MomentumChange1Week            *float64 `json:"momentum_change_1week" bson:"momentum_change_1week"`
	VolumeMomentum1Week            *float64 `json:"volume_momentum_1week" bson:"volume_momentum_1week"`
	VolumeMomentumChange1Week      *float64 `json:"volume_momentum_change_1week" bson:"volume_momentum_change_1week"`
	Volatility1Year                *float64 `json:"volatility_1year" bson:"volatility_1year"`
	Momentum1Year                  *float64 `json:"momentum_1year" bson:"momentum_1year"`
	MomentumChange1Year            *float64 `json:"momentum_change_1year" bson:"momentum_change_1year"`
	VolumeMomentum1Year            *float64 `json:"volume_momentum_1year" bson:"volume_momentum_1year"`
	VolumeMomentumChange1Year      *float64 `json:"volume_momentum_change_1year" bson:"volume_momentum_change_1year"`
	VolatilityYTD                  *float64 `json:"volatility_ytd" bson:"volatility_ytd"`
	MomentumYTD                    *float64 `json:"momentum_ytd" bson:"momentum_ytd"`
	MomentumChangeYTD              *float64 `json:"momentum_change_ytd" bson:"momentum_change_ytd"`
	VolumeMomentumYTD              *float64 `json:"volume_momentum_ytd" bson:"volume_momentum_ytd"`
	VolumeMomentumChangeYTD        *float64 `json:"volume_momentum_change_ytd" bson:"volume_momentum_change_ytd"`
	Volatility24Hr                 *float64 `json:"volatility_24hr" bson:"volatility_24hr"`
	Momentum24Hr                   *float64 `json:"momentum_24hr" bson:"momentum_24hr"`
	MomentumChange24Hr             *float64 `json:"momentum_change_24hr" bson:"momentum_change_24hr"`
	VolumeMomentum24Hr             *float64 `json:"volume_momentum_24hr" bson:"volume_momentum_24hr"`
	VolumeMomentumChange24Hr       *float64 `json:"volume_momentum_change_24hr" bson:"volume_momentum_change_24hr"`
	MarketCap                      float64  `json:"market_cap" bson:"market_cap"`
}

type CacheEntry struct {
	Data      VolatilityData `json:"data"`
	Timestamp time.Time      `json:"timestamp"`
}

type VolatilityCache struct {
	cache map[string]CacheEntry
	mutex sync.RWMutex
}

type BatchOperations struct {
	pendingInserts map[string][]interface{}
	lastFlush      time.Time
	mutex          sync.Mutex
}

type ChangeDetector struct {
	lastDataSnapshot map[string]PriceData
	mutex            sync.RWMutex
}

type CacheStats struct {
	TotalEntries   int `json:"total_entries"`
	ValidEntries   int `json:"valid_entries"`
	ExpiredEntries int `json:"expired_entries"`
}

// Global variables
var (
	// MongoDB collections
	client                     *mongo.Client
	collectionPriceCombined    *mongo.Collection
	collectionLive             *mongo.Collection
	collectionMerged           *mongo.Collection
	dbCap                      *mongo.Database
	
	// Cache and operations
	volatilityCache *VolatilityCache
	batchOps        *BatchOperations
	changeDetector  *ChangeDetector
	
	// Lagos timezone location
	lagosLocation *time.Location
	
	// Stock symbols
	symbols = []string{
		"ABBEYBDS", "ACADEMY", "ACCESSCORP", "AFRIPRUD", "AFRINSURE", "AFROMEDIA",
		"AIICO", "AIRTELAFRI", "ALEX", "ASOSAVINGS", "ABCTRANS", "AUSTINLAZ",
		"MANSARD", "BERGER", "BETAGLAS", "BUACEMENT", "BUAFOODS", "CILEASING",
		"CADBURY", "CAP", "CAPOIL", "CAVERTON", "CHAMPION", "CHAMS", "CHELLARAM",
		"CONOIL", "CORNERST", "WAPIC", "CUSTODIAN", "CUTIX", "CWG", "DAARCOMM",
		"DANGCEM", "DANGSUGAR", "DEAPCAP", "DUNLOP", "ETRANZACT", "ETI", "EKOCORP",
		"ELLAHLAKES", "ETERNA", "EUNISELL", "FBNH", "FCMB", "FIDELITYBK", "FIDSON",
		"FLOURMILL", "FTNCOCOA", "GEREGU", "GOLDBREW", "GOLDINSURE", "VANLEER",
		"GTCO", "GUINEAINS", "GUINNESS", "HONYFLOUR", "IKEJAHOTEL", "IMG",
		"INFINITY", "INTBREW", "INTENEGINS", "JAIZBANK", "JAPAULGOLD", "JOHNHOLT",
		"JULI", "JBERGER", "WAPCO", "LASACO", "LEARNAFRCA", "LINKASSURE",
		"LIVESTOCK", "LIVINGTRUST", "MAYBAKER", "MCNICHOLS", "MEDVIEWAIR",
		"MEYER", "MORISON", "MRS", "MTNN", "MULTITREX", "MULTIVERSE", "MBENEFIT",
		"NNFM", "NASCON", "NCR", "NEIMETH", "NEM", "NESTLE", "NAHCO", "NB",
		"ENAMELWA", "NGXGROUP", "NOTORE", "NPFMCRFBK", "OANDO", "OKOMUOIL",
		"OMATEK", "PZ", "PHARMDEKO", "PREMPAINTS", "PRESCO", "PRESTIGE",
		"RTBRISCOE", "REDSTAREX", "REGALINS", "RONCHESS", "ROYALEX", "SCOA",
		"NSLTECH", "SEPLAT", "SFSREIT", "SKYAVN", "SMURFIT", "SOVRENINS",
		"STACO", "STANBIC", "STDINSURE", "STERLINGNG", "SUNUASSUR", "TANTALIZER",
		"TIP", "THOMASWY", "TOTAL", "TOURIST", "TRANSEXPR", "TRANSCOHOT",
		"TRANSCORP", "TRIPPLEG", "UACN", "UHOMREIT", "UNILEVER", "UBN",
		"UNIONDICON", "UNHOMES", "UBA", "UCAP", "UNITYBNK", "UNIVINSURE",
		"UPL", "UPDC", "UPDCREIT", "VERITASKAP", "VFDGROUP", "VITAFOAM",
		"WEMABANK", "ZENITHBANK",
	}
)

// Initialize global instances
func init() {
	var err error
	lagosLocation, err = time.LoadLocation("Africa/Lagos")
	if err != nil {
		log.Fatal("Failed to load Lagos timezone:", err)
	}
	
	volatilityCache = NewVolatilityCache()
	batchOps = NewBatchOperations()
	changeDetector = NewChangeDetector()
}

// VolatilityCache methods
func NewVolatilityCache() *VolatilityCache {
	vc := &VolatilityCache{
		cache: make(map[string]CacheEntry),
	}
	vc.loadCache()
	return vc
}

func (vc *VolatilityCache) loadCache() {
	vc.mutex.Lock()
	defer vc.mutex.Unlock()
	
	file, err := os.Open(CacheFileName)
	if err != nil {
		if !os.IsNotExist(err) {
			log.Printf("Error opening cache file: %v", err)
		}
		return
	}
	defer file.Close()
	
	if err := json.NewDecoder(file).Decode(&vc.cache); err != nil {
		log.Printf("Error decoding cache: %v", err)
		return
	}
	
	log.Printf("Loaded volatility cache with %d entries", len(vc.cache))
}

func (vc *VolatilityCache) saveCache() {
	vc.mutex.RLock()
	defer vc.mutex.RUnlock()
	
	file, err := os.Create(CacheFileName)
	if err != nil {
		log.Printf("Error creating cache file: %v", err)
		return
	}
	defer file.Close()
	
	if err := json.NewEncoder(file).Encode(vc.cache); err != nil {
		log.Printf("Error encoding cache: %v", err)
		return
	}
	
	log.Printf("Saved volatility cache with %d entries", len(vc.cache))
}

func (vc *VolatilityCache) isCacheValid(symbol string) bool {
	vc.mutex.RLock()
	defer vc.mutex.RUnlock()
	
	entry, exists := vc.cache[symbol]
	if !exists {
		return false
	}
	
	return time.Since(entry.Timestamp) < VolatilityCacheDuration
}

func (vc *VolatilityCache) getCachedData(symbol string) (*VolatilityData, bool) {
	if vc.isCacheValid(symbol) {
		vc.mutex.RLock()
		entry := vc.cache[symbol]
		vc.mutex.RUnlock()
		
		log.Printf("Using cached volatility data for %s", symbol)
		return &entry.Data, true
	}
	return nil, false
}

func (vc *VolatilityCache) setCachedData(symbol string, data VolatilityData) {
	vc.mutex.Lock()
	defer vc.mutex.Unlock()
	
	vc.cache[symbol] = CacheEntry{
		Data:      data,
		Timestamp: time.Now(),
	}
	
	log.Printf("Cached volatility data for %s", symbol)
	
	// Save to disk periodically
	if len(vc.cache)%10 == 0 {
		go vc.saveCache()
	}
}

func (vc *VolatilityCache) clearExpiredCache() {
	vc.mutex.Lock()
	defer vc.mutex.Unlock()
	
	now := time.Now()
	expiredSymbols := make([]string, 0)
	
	for symbol, entry := range vc.cache {
		if now.Sub(entry.Timestamp) >= VolatilityCacheDuration {
			expiredSymbols = append(expiredSymbols, symbol)
		}
	}
	
	for _, symbol := range expiredSymbols {
		delete(vc.cache, symbol)
		log.Printf("Removed expired cache for %s", symbol)
	}
	
	if len(expiredSymbols) > 0 {
		go vc.saveCache()
	}
}

func (vc *VolatilityCache) getCacheStats() CacheStats {
	vc.mutex.RLock()
	defer vc.mutex.RUnlock()
	
	total := len(vc.cache)
	valid := 0
	
	for _, entry := range vc.cache {
		if time.Since(entry.Timestamp) < VolatilityCacheDuration {
			valid++
		}
	}
	
	return CacheStats{
		TotalEntries:   total,
		ValidEntries:   valid,
		ExpiredEntries: total - valid,
	}
}

// BatchOperations methods
func NewBatchOperations() *BatchOperations {
	return &BatchOperations{
		pendingInserts: make(map[string][]interface{}),
		lastFlush:      time.Now(),
	}
}

func (bo *BatchOperations) addDocument(collectionName string, document interface{}) {
	bo.mutex.Lock()
	defer bo.mutex.Unlock()
	
	bo.pendingInserts[collectionName] = append(bo.pendingInserts[collectionName], document)
	
	// Auto-flush if batch is full
	if len(bo.pendingInserts[collectionName]) >= BatchSize {
		go bo.flushCollection(collectionName)
	}
}

func (bo *BatchOperations) flushCollection(collectionName string) bool {
	bo.mutex.Lock()
	docs := bo.pendingInserts[collectionName]
	bo.pendingInserts[collectionName] = nil
	bo.mutex.Unlock()
	
	if len(docs) == 0 {
		return true
	}
	
	collection := bo.getCollection(collectionName)
	if collection == nil {
		return false
	}
	
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	
	_, err := collection.InsertMany(ctx, docs)
	if err != nil {
		log.Printf("Error in batch insert to %s: %v", collectionName, err)
		return false
	}
	
	log.Printf("Batch inserted %d documents to %s", len(docs), collectionName)
	return true
}

func (bo *BatchOperations) flushAll() {
	bo.mutex.Lock()
	collections := make([]string, 0, len(bo.pendingInserts))
	for collection := range bo.pendingInserts {
		collections = append(collections, collection)
	}
	bo.lastFlush = time.Now()
	bo.mutex.Unlock()
	
	for _, collection := range collections {
		bo.flushCollection(collection)
	}
}

func (bo *BatchOperations) getCollection(collectionName string) *mongo.Collection {
	switch collectionName {
	case "live":
		return collectionLive
	case "price_combined":
		return collectionPriceCombined
	case "merged":
		return collectionMerged
	default:
		// Handle date-based collections
		return client.Database("livelake3").Collection(collectionName)
	}
}

func (bo *BatchOperations) shouldAutoFlush() bool {
	bo.mutex.Lock()
	defer bo.mutex.Unlock()
	return time.Since(bo.lastFlush) >= FlushInterval
}

// ChangeDetector methods
func NewChangeDetector() *ChangeDetector {
	return &ChangeDetector{
		lastDataSnapshot: make(map[string]PriceData),
	}
}

func (cd *ChangeDetector) hasSignificantChange(symbol string, newData PriceData, threshold float64) bool {
	cd.mutex.Lock()
	defer cd.mutex.Unlock()
	
	oldData, exists := cd.lastDataSnapshot[symbol]
	if !exists {
		cd.lastDataSnapshot[symbol] = newData
		return true
	}
	
	// Check price change
	var priceChange float64
	if oldData.Close == 0 {
		if newData.Close != 0 {
			priceChange = math.Inf(1)
		} else {
			priceChange = 0
		}
	} else {
		priceChange = math.Abs((newData.Close - oldData.Close) / oldData.Close)
	}
	
	// Check volume change
	var volumeChange float64
	if oldData.Volume == 0 {
		if newData.Volume != 0 {
			volumeChange = math.Inf(1)
		} else {
			volumeChange = 0
		}
	} else {
		volumeChange = math.Abs(float64(newData.Volume-oldData.Volume) / float64(oldData.Volume))
	}
	
	// Update if significant change
	if priceChange >= threshold || volumeChange >= threshold {
		cd.lastDataSnapshot[symbol] = newData
		return true
	}
	
	return false
}

// Utility functions
func safeFloat(value float64) *float64 {
	if math.IsInf(value, 0) || math.IsNaN(value) {
		return nil
	}
	return &value
}

func isMarketOpen() bool {
	now := time.Now().In(lagosLocation)
	
	// Check if it's a weekday (Monday = 1, Sunday = 0)
	if now.Weekday() == time.Saturday || now.Weekday() == time.Sunday {
		return false
	}
	
	// Market hours: 10:00 AM - 2:30 PM
	marketOpen := time.Date(now.Year(), now.Month(), now.Day(), 10, 0, 0, 0, lagosLocation)
	marketClose := time.Date(now.Year(), now.Month(), now.Day(), 14, 30, 0, 0, lagosLocation)
	
	return now.After(marketOpen) && now.Before(marketClose)
}

func connectMongoDB() error {
	mongoURL := os.Getenv("MONGO_URL")
	if mongoURL == "" {
		return fmt.Errorf("MONGO_URL environment variable not set")
	}
	
	clientOptions := options.Client().ApplyURI(mongoURL).SetTLSConfig(nil)
	
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	
	var err error
	client, err = mongo.Connect(ctx, clientOptions)
	if err != nil {
		return fmt.Errorf("failed to connect to MongoDB: %v", err)
	}
	
	// Test the connection
	err = client.Ping(ctx, nil)
	if err != nil {
		return fmt.Errorf("failed to ping MongoDB: %v", err)
	}
	
	// Initialize collections
	dbStockPrices := client.Database("stock_prices_trdv")
	collectionPriceCombined = dbStockPrices.Collection("price_combined_trdv")
	
	dbLive := client.Database("livelake3")
	collectionLive = dbLive.Collection("live_price_combined_trdv")
	collectionMerged = dbLive.Collection("merged_live_price_trdv")
	
	dbCap = client.Database("ngxlistedcompanies")
	
	log.Println("Connected to MongoDB successfully")
	return nil
}

// Mock TradingView data fetching (replace with actual API integration)
func getLiveDataFromTradingView(symbol string) (*PriceData, error) {
	// This is a placeholder - in real implementation, integrate with TradingView API
	// For now, returning mock data
	now := time.Now().In(lagosLocation)
	
	// Simulate some realistic market data
	basePrice := 100.0 + float64(len(symbol))*10.0 // Simple price based on symbol length
	
	return &PriceData{
		DateTime: now.Format("2006-01-02 15:04:05"),
		Open:     basePrice * 0.99,
		High:     basePrice * 1.02,
		Low:      basePrice * 0.98,
		Close:    basePrice,
		Volume:   1000000 + int64(len(symbol)*100000),
		Symbol:   symbol,
		Change:   basePrice * 0.01,
		Percent:  1.0,
	}, nil
}

func getSymbolCap(symbol string) (float64, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	
	collection := dbCap.Collection(symbol)
	
	var result struct {
		SharesOutstanding float64 `bson:"SharesOutstanding"`
	}
	
	err := collection.FindOne(ctx, bson.M{}, options.FindOne().SetProjection(bson.M{"SharesOutstanding": 1, "_id": 0})).Decode(&result)
	if err != nil {
		log.Printf("Error getting market cap for %s: %v", symbol, err)
		return 0, err
	}
	
	return result.SharesOutstanding, nil
}

func getLastAvailableLiveData(symbol string) *PriceData {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	
	// Try merged collection first
	var mergedResult bson.M
	opts := options.FindOne().SetSort(bson.M{"_id": -1}).SetProjection(bson.M{
		"_id": 0, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "change": 1, "percentage_change": 1,
	})
	
	err := collectionMerged.FindOne(ctx, bson.M{"symbol": symbol}, opts).Decode(&mergedResult)
	if err == nil {
		now := time.Now().In(lagosLocation)
		return &PriceData{
			DateTime:   now.Format("2006-01-02 15:04:05"),
			Open:       getFloat64FromBSON(mergedResult, "open"),
			High:       getFloat64FromBSON(mergedResult, "high"),
			Low:        getFloat64FromBSON(mergedResult, "low"),
			Close:      getFloat64FromBSON(mergedResult, "close"),
			Volume:     getInt64FromBSON(mergedResult, "volume"),
			Symbol:     symbol,
			Change:     getFloat64FromBSON(mergedResult, "change"),
			Percent:    getFloat64FromBSON(mergedResult, "percentage_change"),
			IsFallback: true,
		}
	}
	
	// Try live collection
	var liveResult bson.M
	filter := bson.M{symbol: bson.M{"$exists": true}}
	projection := bson.M{"_id": 0, symbol: 1}
	
	err = collectionLive.FindOne(ctx, filter, options.FindOne().SetSort(bson.M{"_id": -1}).SetProjection(projection)).Decode(&liveResult)
	if err == nil {
		if symbolData, ok := liveResult[symbol].(bson.M); ok {
			now := time.Now().In(lagosLocation)
			return &PriceData{
				DateTime:   now.Format("2006-01-02 15:04:05"),
				Open:       getFloat64FromBSON(symbolData, "open"),
				High:       getFloat64FromBSON(symbolData, "high"),
				Low:        getFloat64FromBSON(symbolData, "low"),
				Close:      getFloat64FromBSON(symbolData, "close"),
				Volume:     getInt64FromBSON(symbolData, "volume"),
				Symbol:     symbol,
				Change:     getFloat64FromBSON(symbolData, "change"),
				Percent:    getFloat64FromBSON(symbolData, "percent"),
				IsFallback: true,
			}
		}
	}
	
	// Return default values
	log.Printf("No historical data found for %s, using defaults", symbol)
	now := time.Now().In(lagosLocation)
	return &PriceData{
		DateTime:   now.Format("2006-01-02 15:04:05"),
		Open:       0,
		High:       0,
		Low:        0,
		Close:      0,
		Volume:     0,
		Symbol:     symbol,
		Change:     0,
		Percent:    0,
		IsFallback: true,
	}
}

func getLastAvailableVolatilityData(symbol string) *VolatilityData {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	
	var result VolatilityData
	opts := options.FindOne().SetSort(bson.M{"_id": -1}).SetProjection(bson.M{"_id": 0})
	
	err := collectionPriceCombined.FindOne(ctx, bson.M{"symbol": symbol}, opts).Decode(&result)
	if err == nil {
		result.IsFallback = true
		return &result
	}
	
	// Return default structure
	log.Printf("No historical volatility data found for %s, using defaults", symbol)
	return &VolatilityData{
		Symbol:       symbol,
		CurrentPrice: 0,
		MarketCap:    0,
		IsFallback:   true,
		Timestamp:    time.Now(),
	}
}

func getAllLiveData() map[string]*PriceData {
	combined := make(map[string]*PriceData)
	failedSymbols := make([]string, 0)
	
	for i, symbol := range symbols {
		log.Printf("Fetching live data for %s", symbol)
		data, err := getLiveDataFromTradingView(symbol)
		if err != nil || data == nil {
			log.Printf("Failed to get fresh data for %s, using fallback", symbol)
			failedSymbols = append(failedSymbols, symbol)
			combined[symbol] = getLastAvailableLiveData(symbol)
		} else {
			combined[symbol] = data
		}
		
		// Add small delay between requests
		if i < len(symbols)-1 {
			time.Sleep(500 * time.Millisecond)
		}
	}
	
	if len(failedSymbols) > 0 {
		log.Printf("Used fallback data for %d symbols: %v", len(failedSymbols), failedSymbols)
	}
	
	return combined
}

func calculateComprehensiveMetrics(symbol string) *VolatilityData {
	// Check if cached data is available and valid
	if cachedData, found := volatilityCache.getCachedData(symbol); found {
		// Update current price with fresh live data
		if liveData, err := getLiveDataFromTradingView(symbol); err == nil && liveData != nil {
			cachedData.CurrentPrice = liveData.Close
			// Recalculate market cap with new price
			if sharesOutstanding, err := getSymbolCap(symbol); err == nil {
				cachedData.MarketCap = sharesOutstanding * liveData.Close
			}
		}
		return cachedData
	}
	
	// If no valid cached data, calculate fresh metrics
	log.Printf("Calculating fresh volatility metrics for %s (cache miss)", symbol)
	
	// Get live data for current price
	liveData, _ := getLiveDataFromTradingView(symbol)
	currentPrice := 0.0
	if liveData != nil {
		currentPrice = liveData.Close
	}
	
	// Calculate market cap
	marketCap := 0.0
	if sharesOutstanding, err := getSymbolCap(symbol); err == nil {
		marketCap = sharesOutstanding * currentPrice
	}
	
	// For this example, we'll use placeholder volatility calculations
	// In a real implementation, you would fetch historical data and calculate proper metrics
	data := &VolatilityData{
		Symbol:       symbol,
		CurrentPrice: currentPrice,
		MarketCap:    marketCap,
		Timestamp:    time.Now(),
		// Set all volatility metrics to placeholders for now
		// In real implementation, calculate these from historical data
	}
	
	// Cache the calculated data
	volatilityCache.setCachedData(symbol, *data)
	
	return data
}

func createMergedData(liveData map[string]*PriceData, volatilityData map[string]*VolatilityData) map[string]*MergedData {
	combined := make(map[string]*MergedData)
	
	for symbol, liveInfo := range liveData {
		merged := &MergedData{
			DateTime:         liveInfo.DateTime,
			Symbol:           symbol,
			Open:             liveInfo.Open,
			High:             liveInfo.High,
			Low:              liveInfo.Low,
			Close:            liveInfo.Close,
			Volume:           liveInfo.Volume,
			Change:           liveInfo.Change,
			PercentageChange: liveInfo.Percent,
			CurrentPrice:     liveInfo.Close,
		}
		
		if volData, exists := volatilityData[symbol]; exists {
			merged.Volatility = volData.Volatility
			merged.Momentum = volData.Momentum
			merged.MomentumChange = volData.MomentumChange
			merged.VolumeMomentum = volData.VolumeMomentum
			merged.VolumeMomentumChange = volData.VolumeMomentumChange
			merged.Volatility1Week = volData.Volatility1Week
			merged.Momentum1Week = volData.Momentum1Week
			merged.MomentumChange1Week = volData.MomentumChange1Week
			merged.VolumeMomentum1Week = volData.VolumeMomentum1Week
			merged.VolumeMomentumChange1Week = volData.VolumeMomentumChange1Week
			merged.Volatility1Year = volData.Volatility1Year
			merged.Momentum1Year = volData.Momentum1Year
			merged.MomentumChange1Year = volData.MomentumChange1Year
			merged.VolumeMomentum1Year = volData.VolumeMomentum1Year
			merged.VolumeMomentumChange1Year = volData.VolumeMomentumChange1Year
			merged.VolatilityYTD = volData.VolatilityYTD
			merged.MomentumYTD = volData.MomentumYTD
			merged.MomentumChangeYTD = volData.MomentumChangeYTD
			merged.VolumeMomentumYTD = volData.VolumeMomentumYTD
			merged.VolumeMomentumChangeYTD = volData.VolumeMomentumChangeYTD
			merged.Volatility24Hr = volData.Volatility24Hr
			merged.Momentum24Hr = volData.Momentum24Hr
			merged.MomentumChange24Hr = volData.MomentumChange24Hr
			merged.VolumeMomentum24Hr = volData.VolumeMomentum24Hr
			merged.VolumeMomentumChange24Hr = volData.VolumeMomentumChange24Hr
			merged.MarketCap = volData.MarketCap
		}
		
		combined[symbol] = merged
	}
	
	return combined
}

func saveData(liveData map[string]*PriceData, volatilityData map[string]*VolatilityData, mergedData map[string]*MergedData) map[string]int {
	savedCounts := map[string]int{"live": 0, "volatility": 0, "merged": 0}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	
	// Save live data
	if len(liveData) > 0 {
		liveDocument := make(bson.M)
		for symbol, data := range liveData {
			liveDocument[symbol] = data
		}
		
		_, err := collectionLive.InsertOne(ctx, liveDocument)
		if err != nil {
			log.Printf("Error saving live data: %v", err)
		} else {
			savedCounts["live"] = len(liveData)
			log.Printf("Saved live data for %d symbols", len(liveData))
		}
		
		// Also save to today's collection
		todayStr := time.Now().Format("2006-01-02")
		todayCollection := client.Database("livelake3").Collection(todayStr)
		todayCollection.InsertOne(ctx, liveDocument)
	}
	
	// Save volatility data
	if len(volatilityData) > 0 {
		volatilityDocuments := make([]interface{}, 0)
		for _, volData := range volatilityData {
			if !volData.IsFallback {
				volData.Timestamp = time.Now().In(lagosLocation)
				volatilityDocuments = append(volatilityDocuments, volData)
			}
		}
		
		if len(volatilityDocuments) > 0 {
			_, err := collectionPriceCombined.InsertMany(ctx, volatilityDocuments)
			if err != nil {
				log.Printf("Error saving volatility data: %v", err)
			} else {
				savedCounts["volatility"] = len(volatilityDocuments)
				log.Printf("Saved %d fresh volatility records", len(volatilityDocuments))
			}
		}
	}
	
	// Save merged data
	if len(mergedData) > 0 {
		combinedDocument := make(bson.M)
		for symbol, merged := range mergedData {
			// Remove symbol field as it becomes the key
			mergedBSON := toBSON(merged)
			delete(mergedBSON, "symbol")
			combinedDocument[symbol] = mergedBSON
		}
		
		_, err := collectionMerged.InsertOne(ctx, combinedDocument)
		if err != nil {
			log.Printf("Error saving combined merged data: %v", err)
		} else {
			savedCounts["merged"] = len(mergedData)
			log.Printf("Saved combined merged document with %d symbols", len(mergedData))
		}
	}
	
	return savedCounts
}

func mainCycle() {
	if !isMarketOpen() {
		log.Println("Market closed")
		return
	}
	
	log.Println("Market is open - Starting data collection (live: fresh, volatility: 1hr cache)")
	
	// Clear expired cache entries
	volatilityCache.clearExpiredCache()
	
	// Get cache statistics
	cacheStats := volatilityCache.getCacheStats()
	log.Printf("Cache status: %d valid, %d expired, %d total", 
		cacheStats.ValidEntries, cacheStats.ExpiredEntries, cacheStats.TotalEntries)
	
	// Step 1: Get live data for all symbols
	log.Println("Step 1: Fetching live data from TradingView...")
	liveData := getAllLiveData()
	
	if len(liveData) == 0 {
		log.Println("No live data retrieved")
		return
	}
	
	// Step 2: Calculate volatility metrics with caching
	log.Println("Step 2: Calculating volatility and momentum metrics (with 1hr caching)...")
	volatilityData := make(map[string]*VolatilityData)
	failedVolatilitySymbols := make([]string, 0)
	cacheHits := 0
	cacheMisses := 0
	
	for i, symbol := range symbols {
		if cachedData, found := volatilityCache.getCachedData(symbol); found {
			cacheHits++
			volatilityData[symbol] = cachedData
			// Update current price with fresh live data
			if liveInfo, exists := liveData[symbol]; exists {
				volatilityData[symbol].CurrentPrice = liveInfo.Close
				// Recalculate market cap with new price
				if sharesOutstanding, err := getSymbolCap(symbol); err == nil {
					volatilityData[symbol].MarketCap = sharesOutstanding * liveInfo.Close
				}
			}
			log.Printf("Using cached data for %s", symbol)
		} else {
			cacheMisses++
			log.Printf("Making fresh API call for %s (cache miss)", symbol)
			metrics := calculateComprehensiveMetrics(symbol)
			if metrics != nil {
				volatilityData[symbol] = metrics
				log.Printf("Successfully calculated fresh metrics for %s", symbol)
			} else {
				log.Printf("API call failed for %s, using fallback data", symbol)
				failedVolatilitySymbols = append(failedVolatilitySymbols, symbol)
				volatilityData[symbol] = getLastAvailableVolatilityData(symbol)
			}
			
			// Add delay to avoid API overload
			if i < len(symbols)-1 {
				time.Sleep(2 * time.Second)
			}
		}
	}
	
	hitRate := 0.0
	if cacheHits+cacheMisses > 0 {
		hitRate = float64(cacheHits) / float64(cacheHits+cacheMisses) * 100
	}
	
	log.Printf("Cache performance: %d hits, %d misses (hit rate: %.1f%%)", cacheHits, cacheMisses, hitRate)
	log.Printf("Fresh volatility calculations: %d", cacheMisses)
	
	if len(failedVolatilitySymbols) > 0 {
		log.Printf("Used fallback volatility data for %d symbols: %v", len(failedVolatilitySymbols), failedVolatilitySymbols)
	}
	
	// Ensure all symbols from live_data have corresponding volatility data
	for symbol := range liveData {
		if _, exists := volatilityData[symbol]; !exists {
			log.Printf("Adding fallback volatility data for missing symbol: %s", symbol)
			volatilityData[symbol] = getLastAvailableVolatilityData(symbol)
		}
	}
	
	// Step 3: Create merged data
	log.Println("Step 3: Merging data...")
	mergedData := createMergedData(liveData, volatilityData)
	
	// Step 4: Save data
	log.Println("Step 4: Saving data...")
	savedCounts := saveData(liveData, volatilityData, mergedData)
	
	// Step 5: Save cache to disk
	volatilityCache.saveCache()
	
	log.Printf("Data cycle completed successfully - %d symbols processed", len(liveData))
	log.Printf("Saved - Live: %d, Volatility: %d, Merged: %d", 
		savedCounts["live"], savedCounts["volatility"], savedCounts["merged"])
	
	// Summary statistics
	freshLiveCount := 0
	fallbackLiveCount := 0
	for _, data := range liveData {
		if data.IsFallback {
			fallbackLiveCount++
		} else {
			freshLiveCount++
		}
	}
	
	freshVolCount := 0
	fallbackVolCount := 0
	for _, data := range volatilityData {
		if data.IsFallback {
			fallbackVolCount++
		} else {
			freshVolCount++
		}
	}
	
	log.Printf("Live data - Fresh: %d, Fallback: %d", freshLiveCount, fallbackLiveCount)
	log.Printf("Volatility data - Fresh: %d, Fallback: %d", freshVolCount, fallbackVolCount)
	log.Printf("Volatility cache performance: %d hits, %d misses", cacheHits, cacheMisses)
	log.Printf("Total symbols expected: %d, Total symbols saved: %d", len(symbols), len(mergedData))
	
	if len(mergedData) != len(symbols) {
		missingSymbols := make([]string, 0)
		for _, symbol := range symbols {
			if _, exists := mergedData[symbol]; !exists {
				missingSymbols = append(missingSymbols, symbol)
			}
		}
		log.Printf("WARNING: Missing symbols in final dataset: %v", missingSymbols)
	}
}

func runUnifiedSystem() {
	log.Println("Starting Unified Price System - Live Data Fresh, Volatility Data with 1-Hour Cache")
	log.Println("Live data: fetched every 20 minutes during market hours (10 AM - 2:30 PM weekdays)")
	log.Println("Volatility data: calculated fresh on cache miss, reused for 1 hour on cache hit")
	
	ticker := time.NewTicker(UpdateInterval)
	defer ticker.Stop()
	
	for {
		select {
		case <-ticker.C:
			now := time.Now().In(lagosLocation)
			
			if isMarketOpen() {
				log.Println(strings.Repeat("=", 60))
				log.Printf("Market is open - Starting data fetch at %s", now.Format("2006-01-02 15:04:05"))
				
				mainCycle()
				
				nextUpdate := now.Add(UpdateInterval)
				log.Printf("Next update in 20 minutes - %s", nextUpdate.Format("2006-01-02 15:04:05"))
				log.Println(strings.Repeat("=", 60))
			} else {
				log.Println("Market closed or weekend - waiting for next market session")
			}
		}
	}
}

// Utility functions for BSON conversion
func getFloat64FromBSON(m bson.M, key string) float64 {
	if val, ok := m[key]; ok {
		switch v := val.(type) {
		case float64:
			return v
		case float32:
			return float64(v)
		case int:
			return float64(v)
		case int32:
			return float64(v)
		case int64:
			return float64(v)
		}
	}
	return 0
}

func getInt64FromBSON(m bson.M, key string) int64 {
	if val, ok := m[key]; ok {
		switch v := val.(type) {
		case int64:
			return v
		case int:
			return int64(v)
		case int32:
			return int64(v)
		case float64:
			return int64(v)
		case float32:
			return int64(v)
		}
	}
	return 0
}

func toBSON(v interface{}) bson.M {
	data, _ := bson.Marshal(v)
	var result bson.M
	bson.Unmarshal(data, &result)
	return result
}

// Public utility functions
func ClearVolatilityCache() {
	volatilityCache.cache = make(map[string]CacheEntry)
	volatilityCache.saveCache()
	log.Println("Volatility cache cleared")
}

func GetCacheInfo() CacheStats {
	stats := volatilityCache.getCacheStats()
	log.Printf("Volatility Cache Information:")
	log.Printf("  Total entries: %d", stats.TotalEntries)
	log.Printf("  Valid entries: %d", stats.ValidEntries)
	log.Printf("  Expired entries: %d", stats.ExpiredEntries)
	log.Printf("  Cache duration: %.0f minutes (%.2f hours)", VolatilityCacheDuration.Minutes(), VolatilityCacheDuration.Hours())
	
	if stats.TotalEntries > 0 {
		hitPotential := float64(stats.ValidEntries) / float64(stats.TotalEntries) * 100
		log.Printf("  Cache hit potential: %.1f%%", hitPotential)
	}
	
	return stats
}

func ForceCacheRefresh(symbol string) {
	if symbol == "" {
		volatilityCache.cache = make(map[string]CacheEntry)
		log.Println("Cleared all cache entries")
	} else {
		volatilityCache.mutex.Lock()
		if _, exists := volatilityCache.cache[symbol]; exists {
			delete(volatilityCache.cache, symbol)
			log.Printf("Cleared cache for %s", symbol)
		} else {
			log.Printf("No cache entry found for %s", symbol)
		}
		volatilityCache.mutex.Unlock()
	}
	
	volatilityCache.saveCache()
}

func main() {
	// Load environment variables if using a .env file
	// You might want to use a library like godotenv for this
	
	// Connect to MongoDB
	if err := connectMongoDB(); err != nil {
		log.Fatal("Failed to connect to MongoDB:", err)
	}
	defer func() {
		if err := client.Disconnect(context.Background()); err != nil {
			log.Printf("Error disconnecting from MongoDB: %v", err)
		}
	}()
	
	// Run the unified system
	runUnifiedSystem()
}
