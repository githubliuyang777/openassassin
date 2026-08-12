package main

import (
	"context"
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

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	reporter := NewReporter(cfg.ServerURL, cfg.Token, cfg.Hostname, Version)
	eventCollector := NewEventCollector()
	eventCollector.StartDockerListener(ctx)

	// Report immediately on start
	reportOnce(reporter, eventCollector)

	ticker := time.NewTicker(time.Duration(cfg.Interval) * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			reportOnce(reporter, eventCollector)
		case sig := <-sigCh:
			log.Printf("Received signal %v, shutting down", sig)
			cancel()
			return
		}
	}
}

func reportOnce(r *Reporter, ec *EventCollector) {
	// Collect OOM events
	ec.CollectOOM()

	// Report metrics
	metrics, err := Collect()
	if err != nil {
		log.Printf("ERROR: failed to collect metrics: %v", err)
	} else {
		if err := r.Report(metrics); err != nil {
			// Reporter already logs internally
		}
	}

	// Report events
	events := ec.DrainEvents()
	if len(events) > 0 {
		if err := r.ReportEvents(events); err != nil {
			log.Printf("WARN: failed to report %d events: %v", len(events), err)
		}
	}
}
