package main

import (
	"time"

	"github.com/shirou/gopsutil/v4/cpu"
	"github.com/shirou/gopsutil/v4/disk"
	"github.com/shirou/gopsutil/v4/host"
	"github.com/shirou/gopsutil/v4/load"
	"github.com/shirou/gopsutil/v4/mem"
	"github.com/shirou/gopsutil/v4/net"
	"github.com/shirou/gopsutil/v4/process"
)

type Metrics struct {
	CPUPercent   float64 `json:"cpu_percent"`
	MemPercent   float64 `json:"mem_percent"`
	MemTotalMB   float64 `json:"mem_total_mb"`
	MemUsedMB    float64 `json:"mem_used_mb"`
	DiskPercent  float64 `json:"disk_percent"`
	DiskTotalGB  float64 `json:"disk_total_gb"`
	DiskUsedGB   float64 `json:"disk_used_gb"`
	Load1m       float64 `json:"load_1m"`
	Load5m       float64 `json:"load_5m"`
	Load15m      float64 `json:"load_15m"`
	NetRxBytes   uint64  `json:"net_rx_bytes"`
	NetTxBytes   uint64  `json:"net_tx_bytes"`
	ProcessCount int     `json:"process_count"`
	UptimeSeconds uint64 `json:"uptime_seconds"`
}

func Collect() (*Metrics, error) {
	m := &Metrics{}

	// CPU (wait 200ms for a reading)
	if percents, err := cpu.Percent(200*time.Millisecond, false); err == nil && len(percents) > 0 {
		m.CPUPercent = round(percents[0], 1)
	}

	// Memory
	if vmem, err := mem.VirtualMemory(); err == nil {
		m.MemPercent = round(vmem.UsedPercent, 1)
		m.MemTotalMB = round(float64(vmem.Total)/1024/1024, 1)
		m.MemUsedMB = round(float64(vmem.Used)/1024/1024, 1)
	}

	// Disk (root partition only)
	if du, err := disk.Usage("/"); err == nil {
		m.DiskPercent = round(du.UsedPercent, 1)
		m.DiskTotalGB = round(float64(du.Total)/1024/1024/1024, 1)
		m.DiskUsedGB = round(float64(du.Used)/1024/1024/1024, 1)
	}

	// Load averages
	if lavg, err := load.Avg(); err == nil {
		m.Load1m = round(lavg.Load1, 2)
		m.Load5m = round(lavg.Load5, 2)
		m.Load15m = round(lavg.Load15, 2)
	}

	// Network (sum all except loopback)
	if counters, err := net.IOCounters(false); err == nil {
		var rx, tx uint64
		for _, c := range counters {
			if c.Name == "lo" {
				continue
			}
			rx += c.BytesRecv
			tx += c.BytesSent
		}
		m.NetRxBytes = rx
		m.NetTxBytes = tx
	}

	// Process count
	if pids, err := process.Pids(); err == nil {
		m.ProcessCount = len(pids)
	}

	// Uptime
	if uptime, err := host.Uptime(); err == nil {
		m.UptimeSeconds = uptime
	}

	return m, nil
}

func round(val float64, precision int) float64 {
	pow := 1.0
	for i := 0; i < precision; i++ {
		pow *= 10
	}
	return float64(int(val*pow+0.5)) / pow
}
