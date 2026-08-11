package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"
)

const (
	maxBufferSize = 100
	reportTimeout = 10 * time.Second
)

type ReportPayload struct {
	Hostname      string  `json:"hostname"`
	AgentVersion  string  `json:"agent_version"`
	CPUPercent    float64 `json:"cpu_percent"`
	MemPercent    float64 `json:"mem_percent"`
	MemTotalMB    float64 `json:"mem_total_mb"`
	MemUsedMB     float64 `json:"mem_used_mb"`
	DiskPercent   float64 `json:"disk_percent"`
	DiskTotalGB   float64 `json:"disk_total_gb"`
	DiskUsedGB    float64 `json:"disk_used_gb"`
	Load1m        float64 `json:"load_1m"`
	Load5m        float64 `json:"load_5m"`
	Load15m       float64 `json:"load_15m"`
	NetRxBytes    uint64  `json:"net_rx_bytes"`
	NetTxBytes    uint64  `json:"net_tx_bytes"`
	ProcessCount  int     `json:"process_count"`
	UptimeSeconds uint64  `json:"uptime_seconds"`
}

type Reporter struct {
	serverURL string
	token     string
	hostname  string
	version   string
	client    *http.Client
	buf       []*ReportPayload
}

func NewReporter(serverURL, token, hostname, version string) *Reporter {
	return &Reporter{
		serverURL: serverURL,
		token:     token,
		hostname:  hostname,
		version:   version,
		client:    &http.Client{Timeout: reportTimeout},
		buf:       make([]*ReportPayload, 0, maxBufferSize),
	}
}

func (r *Reporter) Report(m *Metrics) error {
	payload := &ReportPayload{
		Hostname:      r.hostname,
		AgentVersion:  r.version,
		CPUPercent:    m.CPUPercent,
		MemPercent:    m.MemPercent,
		MemTotalMB:    m.MemTotalMB,
		MemUsedMB:     m.MemUsedMB,
		DiskPercent:   m.DiskPercent,
		DiskTotalGB:   m.DiskTotalGB,
		DiskUsedGB:    m.DiskUsedGB,
		Load1m:        m.Load1m,
		Load5m:        m.Load5m,
		Load15m:       m.Load15m,
		NetRxBytes:    m.NetRxBytes,
		NetTxBytes:    m.NetTxBytes,
		ProcessCount:  m.ProcessCount,
		UptimeSeconds: m.UptimeSeconds,
	}

	// Try to drain buffer first
	r.drainBuffer()

	// Send current payload
	if err := r.send(payload); err != nil {
		r.bufferPush(payload)
		return err
	}

	return nil
}

func (r *Reporter) send(payload *ReportPayload) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal: %w", err)
	}

	url := r.serverURL + "/api/v1/agents/report"
	req, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+r.token)

	resp, err := r.client.Do(req)
	if err != nil {
		log.Printf("WARN: report failed: %v", err)
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		log.Printf("WARN: report returned HTTP %d", resp.StatusCode)
		return fmt.Errorf("HTTP %d", resp.StatusCode)
	}

	return nil
}

func (r *Reporter) bufferPush(payload *ReportPayload) {
	if len(r.buf) >= maxBufferSize {
		r.buf = r.buf[1:]
	}
	r.buf = append(r.buf, payload)
	log.Printf("WARN: buffered report (buffer: %d/%d)", len(r.buf), maxBufferSize)
}

func (r *Reporter) drainBuffer() {
	for len(r.buf) > 0 {
		payload := r.buf[0]
		if err := r.send(payload); err != nil {
			return
		}
		r.buf = r.buf[1:]
	}
}
