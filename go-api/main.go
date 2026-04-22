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
	"time"

	_ "github.com/lib/pq"
)

var db *sql.DB

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
	db.SetMaxOpenConns(50)
	db.SetMaxIdleConns(10)
	db.SetConnMaxLifetime(5 * time.Minute)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := db.PingContext(ctx); err != nil {
		log.Fatalf("ping db: %v", err)
	}

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

func daysSinceHeavyHandler(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()

	// Workload sintético de alocação
	// Aloca 1MB de dados temporários
	const allocSize = 1 * 1024 * 1024 // 1MB
	buffer := make([]byte, allocSize)

	// Preenche o buffer para forçar alocação real
	for i := 0; i < len(buffer); i += 4096 {
		buffer[i] = byte(i % 256)
	}

	// Faz algum processamento para evitar otimização do compilador
	sum := 0
	for i := 0; i < len(buffer); i += 1024 {
		sum += int(buffer[i])
	}

	// Continua com a lógica normal
	var reference time.Time
	err := db.QueryRowContext(ctx, "SELECT reference_date FROM base_date WHERE id = 1").Scan(&reference)
	if err != nil {
		http.Error(w, "db error", http.StatusInternalServerError)
		return
	}

	days := int(time.Since(reference).Hours() / 24)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"days_since": days,
		"checksum":   sum, // Previne otimização
	})
}

type MetricsResponse struct {
	Timestamp       string  `json:"timestamp"`
	AllocBytes      uint64  `json:"alloc_bytes"`
	TotalAllocBytes uint64  `json:"total_alloc_bytes"`
	SysBytes        uint64  `json:"sys_bytes"`
	HeapAllocBytes  uint64  `json:"heap_alloc_bytes"`
	HeapSysBytes    uint64  `json:"heap_sys_bytes"`
	HeapIdleBytes   uint64  `json:"heap_idle_bytes"`
	HeapInuseBytes  uint64  `json:"heap_inuse_bytes"`
	HeapObjects     uint64  `json:"heap_objects"`
	NumGC           uint32  `json:"num_gc"`
	NumGoroutine    int     `json:"num_goroutine"`
	PauseTotalNs    uint64  `json:"pause_total_ns"`
	LastPauseNs     uint64  `json:"last_pause_ns"`
	AllocRate       float64 `json:"alloc_rate_mb_per_sec"`
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

	metrics := MetricsResponse{
		Timestamp:       now.Format(time.RFC3339),
		AllocBytes:      m.Alloc,
		TotalAllocBytes: m.TotalAlloc,
		SysBytes:        m.Sys,
		HeapAllocBytes:  m.HeapAlloc,
		HeapSysBytes:    m.HeapSys,
		HeapIdleBytes:   m.HeapIdle,
		HeapInuseBytes:  m.HeapInuse,
		HeapObjects:     m.HeapObjects,
		NumGC:           m.NumGC,
		NumGoroutine:    runtime.NumGoroutine(),
		PauseTotalNs:    m.PauseTotalNs,
		LastPauseNs:     lastPause,
		AllocRate:       allocRate,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(metrics)
}
