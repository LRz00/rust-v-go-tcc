package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
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
