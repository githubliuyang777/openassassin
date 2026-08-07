package main

import (
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"
)

var Version = "dev"

func main() {
	cfg := parseConfig()

	log.Printf("host-agent v%s started, reporting to %s every %ds", Version, cfg.ServerURL, cfg.Interval)

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	reporter := NewReporter(cfg.ServerURL, cfg.Token, cfg.Hostname, Version)

	// Report immediately on start
	reportOnce(reporter)

	ticker := time.NewTicker(time.Duration(cfg.Interval) * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			reportOnce(reporter)
		case sig := <-sigCh:
			log.Printf("Received signal %v, shutting down", sig)
			return
		}
	}
}

func reportOnce(r *Reporter) {
	metrics, err := Collect()
	if err != nil {
		log.Printf("ERROR: failed to collect metrics: %v", err)
		return
	}
	if err := r.Report(metrics); err != nil {
		// Reporter already logs internally
		return
	}
}
