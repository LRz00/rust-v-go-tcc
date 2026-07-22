package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"runtime"
	"strconv"
	"strings"
	"sync/atomic"
	"time"

	_ "github.com/lib/pq"
)

var db *sql.DB

func waitForDB(db *sql.DB, maxWait time.Duration) error {
	deadline := time.Now().Add(maxWait)
	attempt := 0

	for {
		attempt++
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		err := db.PingContext(ctx)
		cancel()
		if err == nil {
			return nil
		}

		if time.Now().After(deadline) {
			return fmt.Errorf("db not ready after %s: %w", maxWait, err)
		}

		if attempt == 1 || attempt%5 == 0 {
			log.Printf("DB not ready yet (attempt %d): %v", attempt, err)
		}
		time.Sleep(1 * time.Second)
	}
}

func main() {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		dsn = "host=postgres user=tcc password=tcc dbname=tcc sslmode=disable"
	}

	var err error
	db, err = sql.Open("postgres", dsn)
	if err != nil {
		log.Fatalf("open db: %v", err)
	}
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(5 * time.Minute)

	if err := waitForDB(db, 60*time.Second); err != nil {
		log.Fatalf("ping db: %v", err)
	}

	status, err := readProcSelfStatus()
	log.Printf("VmRSS: %d KB, VmHWM: %d KB, error: %v", status.VmRSSKB, status.VmHWMKB, err)

	http.HandleFunc("/days-since", daysSinceHandler)
	http.HandleFunc("/days-since-heavy", daysSinceHeavyHandler)
	http.HandleFunc("/metrics", metricsHandler)
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("OK"))
	})

	port := "8080"
	if p := os.Getenv("PORT"); p != "" {
		port = p
	}
	addr := fmt.Sprintf(":%s", port)
	log.Printf("Go API listening on %s", addr)
	log.Fatal(http.ListenAndServe(addr, nil))

}

func daysSinceHandler(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()

	var reference time.Time
	err := db.QueryRowContext(ctx, "SELECT reference_date FROM base_date WHERE id = 1").Scan(&reference)
	if err != nil {
		http.Error(w, "db error", http.StatusInternalServerError)
		return
	}

	days := int(time.Since(reference).Hours() / 24)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]int{"days_since": days})
}

var lastHeavyBuffer atomic.Value

func daysSinceHeavyHandler(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()
	seed := time.Now().UnixNano()
	// Workload sintético de alocação
	// Aloca 1MB de dados temporários
	const allocSize = 1 * 1024 * 1024
	buffer := make([]byte, allocSize)

	// Preenche o buffer para forçar alocação real
	for i := 0; i < len(buffer); i += 4096 {
		buffer[i] = byte((int64(i) + seed) % 256)
	}

	// Faz algum processamento para evitar otimização do compilador
	sum := 0
	for i := 0; i < len(buffer); i += 1024 {
		sum += int(buffer[i])
	}

	lastHeavyBuffer.Store(buffer)

	// Continua com a lógica normal
	var reference time.Time
	err := db.QueryRowContext(ctx, "SELECT reference_date FROM base_date WHERE id = 1").Scan(&reference)
	if err != nil {
		http.Error(w, "db error", http.StatusInternalServerError)
		return
	}

	days := int(time.Since(reference).Hours() / 24)
	runtime.KeepAlive(buffer)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"days_since": days,
		"checksum":   sum, // Previne otimização
	})
}

type MemStatusVM struct {
	VmRSSKB uint64 // RSS atual em KB
	VmHWMKB uint64 // Pico de RSS em KB
}

func readProcSelfStatus() (MemStatusVM, error) {
	data, err := os.ReadFile("/proc/self/status")

	if err != nil {
		return MemStatusVM{}, fmt.Errorf("failed to read /proc/self/status: %w", err)
	}

	var result MemStatusVM

	lines := strings.Split(string(data), "\n")

	for _, line := range lines {
		if strings.HasPrefix(line, "VmRSS:") {
			val, err := parseStatusKBLine(line)
			if err == nil {
				result.VmRSSKB = val
			}
		} else if strings.HasPrefix(line, "VmHWM:") {
			val, err := parseStatusKBLine(line)
			if err == nil {
				result.VmHWMKB = val
			}
		}
	}
	return result, nil
}

func parseStatusKBLine(line string) (uint64, error) {
	fields := strings.Fields(line) // ex: ["VmRSS:", "12345", "kB"]
	if len(fields) < 2 {
		return 0, fmt.Errorf("unexpected format: %q", line)
	}
	val, err := strconv.ParseUint(fields[1], 10, 64)
	if err != nil {
		return 0, fmt.Errorf("failed to parse value in %q: %w", line, err)
	}
	return val, nil
}

// CgroupMemStats
type CgroupMemStats struct {
	Version      string
	CurrentBytes uint64
	PeakBytes    uint64
	MaxBytes     uint64
	Unlimited    bool
}

// readCgroupMemStats
func readCGroupMemStats() (CgroupMemStats, error) {
	if stats, err := readCGroupV2(); err == nil {
		return stats, nil
	}

	//fallback to cgroup v1
	if stats, err := readCGroupV1(); err == nil {
		return stats, nil
	}

	return CgroupMemStats{Version: "unknown"}, fmt.Errorf("failed to read cgroup memory stats(v1 and v2)")
}

// readCGroupV2
func readCGroupV2() (CgroupMemStats, error) {
	current, err := readCgroupUintFile("/sys/fs/cgroup/memory.current")
	if err != nil {
		return CgroupMemStats{}, err
	}

	peak, err := readCgroupUintFile("/sys/fs/cgroup/memory.peak")
	if err != nil {
		peak = 0
	}

	maxRaw, err := os.ReadFile("/sys/fs/cgroup/memory.max")
	if err != nil {
		return CgroupMemStats{}, err
	}
	maxStr := strings.TrimSpace(string(maxRaw))

	var maxBytes uint64
	unlimited := false

	if maxStr == "max" {
		unlimited = true
	} else {
		maxBytes, err = strconv.ParseUint(maxStr, 10, 64)
		if err != nil {
			return CgroupMemStats{}, fmt.Errorf("failed to parse memory.max: %w", err)
		}
	}

	return CgroupMemStats{
		Version:      "v2",
		CurrentBytes: current,
		PeakBytes:    peak,
		MaxBytes:     maxBytes,
		Unlimited:    unlimited,
	}, nil
}

// readCGroupV1
func readCGroupV1() (CgroupMemStats, error) {
	current, err := readCgroupUintFile("/sys/fs/cgroup/memory/memory.usage_in_bytes")
	if err != nil {
		return CgroupMemStats{}, err
	}

	peak, err := readCgroupUintFile("/sys/fs/cgroup/memory/memory.max_usage_in_bytes")
	if err != nil {
		peak = 0
	}

	max, err := readCgroupUintFile("/sys/fs/cgroup/memory/memory.limit_in_bytes")
	if err != nil {
		return CgroupMemStats{}, err
	}

	// in cgroup v1, if the limit is set to a very high value, it means unlimited
	const v1UnlimitedThreshold = uint64(1) << 62

	unlimited := max >= v1UnlimitedThreshold

	return CgroupMemStats{
		Version:      "v1",
		CurrentBytes: current,
		PeakBytes:    peak,
		MaxBytes:     max,
		Unlimited:    unlimited,
	}, nil
}

// readCgroupUintFile
func readCgroupUintFile(path string) (uint64, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return 0, err
	}

	val, err := strconv.ParseUint(strings.TrimSpace(string(data)), 10, 64)
	if err != nil {
		return 0, fmt.Errorf("failed to parse uint from %s: %w", path, err)
	}
	return val, nil
}

// these metrics are directly comparable between go and rust
type CommonMemMetrics struct {
	RSSKB              uint64 `json:"rss_kb"`
	PeakRSSKB          uint64 `json:"peak_rss_kb"`
	CgroupVersion      string `json:"cgroup_version"`
	CgroupCurrentBytes uint64 `json:"cgroup_current_bytes"`
	CgroupPeakBytes    uint64 `json:"cgroup_peak_bytes"`
	CgroupMaxBytes     uint64 `json:"cgroup_max_bytes"`
	CgroupUnlimited    bool   `json:"cgroup_unlimited"`
}

// these are go specific metrics
type RuntimeSpecificMetrics struct {
	AllocBytes      uint64  `json:"alloc_bytes"`
	TotalAllocBytes uint64  `json:"total_alloc_bytes"`
	SysBytes        uint64  `json:"sys_bytes"`
	HeapAllocBytes  uint64  `json:"heap_alloc_bytes"`
	HeapSysBytes    uint64  `json:"heap_sys_bytes"`
	HeapIdleBytes   uint64  `json:"heap_idle_bytes"`
	HeapInuseBytes  uint64  `json:"heap_inuse_bytes"`
	HeapObjects     uint64  `json:"heap_objects"`
	NumGC           uint32  `json:"num_gc"`
	PauseTotalNs    uint64  `json:"pause_total_ns"`
	LastPauseNs     uint64  `json:"last_pause_ns"`
	NumGoroutine    int     `json:"num_goroutine"`
	AllocRate       float64 `json:"alloc_rate_mb_per_sec"`
}

type MetricsResponse struct {
	Timestamp string                 `json:"timestamp"`
	Common    CommonMemMetrics       `json:"common"`
	Runtime   RuntimeSpecificMetrics `json:"runtime_specific"`
}

var (
	startTime       = time.Now()
	lastTotalAlloc  uint64
	lastMeasureTime = time.Now()
)

func metricsHandler(w http.ResponseWriter, r *http.Request) {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)

	now := time.Now()
	elapsed := now.Sub(lastMeasureTime).Seconds()

	var allocRate float64
	if elapsed > 0 && lastTotalAlloc > 0 {
		allocDiff := m.TotalAlloc - lastTotalAlloc
		allocRate = float64(allocDiff) / (1024 * 1024) / elapsed
	}

	lastTotalAlloc = m.TotalAlloc
	lastMeasureTime = now

	var lastPause uint64
	if m.NumGC > 0 {
		lastPause = m.PauseNs[(m.NumGC+255)%256]
	}

	var common CommonMemMetrics

	if status, err := readProcSelfStatus(); err == nil {
		common.RSSKB = status.VmRSSKB
		common.PeakRSSKB = status.VmHWMKB
	} else {
		log.Printf("failed to read /proc/self/status: %v", err)
	}

	if cgroup, err := readCGroupMemStats(); err == nil {
		common.CgroupCurrentBytes = cgroup.CurrentBytes
		common.CgroupPeakBytes = cgroup.PeakBytes
		common.CgroupMaxBytes = cgroup.MaxBytes
		common.CgroupUnlimited = cgroup.Unlimited
		common.CgroupVersion = cgroup.Version
	}

	runtimeSpecific := RuntimeSpecificMetrics{
		AllocBytes:      m.Alloc,
		TotalAllocBytes: m.TotalAlloc,
		SysBytes:        m.Sys,
		HeapAllocBytes:  m.HeapAlloc,
		HeapSysBytes:    m.HeapSys,
		HeapIdleBytes:   m.HeapIdle,
		HeapInuseBytes:  m.HeapInuse,
		HeapObjects:     m.HeapObjects,
		NumGC:           m.NumGC,
		PauseTotalNs:    m.PauseTotalNs,
		LastPauseNs:     lastPause,
		NumGoroutine:    runtime.NumGoroutine(),
		AllocRate:       allocRate,
	}

	metrics := MetricsResponse{
		Timestamp: now.Format(time.RFC3339),
		Common:    common,
		Runtime:   runtimeSpecific,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(metrics)
}
