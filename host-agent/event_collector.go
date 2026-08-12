package main

import (
	"bufio"
	"context"
	"log"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/docker/docker/api/types"
	"github.com/docker/docker/api/types/events"
	"github.com/docker/docker/api/types/filters"
	"github.com/docker/docker/client"
)

// SystemEvent represents a system-level event (OOM, container die, etc.)
type SystemEvent struct {
	Timestamp time.Time         `json:"timestamp"`
	Category  string            `json:"category"`  // "oom" | "container"
	Severity  string            `json:"severity"`  // "critical" | "warning" | "info"
	Source    string            `json:"source"`    // "kernel" | "docker"
	Title     string            `json:"title"`
	Detail    string            `json:"detail"`
	Labels    map[string]string `json:"labels"`
}

// EventCollector collects system events from multiple sources
type EventCollector struct {
	mu             sync.Mutex
	events         []*SystemEvent
	lastOOMCount   uint64
	dockerAvailable bool
	maxEvents      int
	dedupWindow    time.Duration
	recentTitles   map[string]time.Time
}

// NewEventCollector creates a new event collector
func NewEventCollector() *EventCollector {
	ec := &EventCollector{
		maxEvents:    100,
		dedupWindow:  5 * time.Minute,
		recentTitles: make(map[string]time.Time),
	}
	// Check Docker availability
	cli, err := client.NewClientWithOpts(client.WithAPIVersionNegotiation())
	if err == nil {
		_, err = cli.Ping(context.Background())
		if err == nil {
			ec.dockerAvailable = true
		}
		cli.Close()
	}
	if ec.dockerAvailable {
		log.Println("Docker daemon detected, container event monitoring enabled")
	} else {
		log.Println("Docker daemon not available, container event monitoring disabled")
	}
	return ec
}

// CollectOOM checks /proc/vmstat for oom_kill count changes
func (ec *EventCollector) CollectOOM() {
	count := readOOMKillCount()
	if count <= ec.lastOOMCount {
		return
	}
	delta := count - ec.lastOOMCount
	ec.lastOOMCount = count

	evt := &SystemEvent{
		Timestamp: time.Now(),
		Category:  "oom",
		Severity:  "critical",
		Source:    "kernel",
		Title:     "OOM Kill detected",
		Detail:    "Out of memory killer invoked " + strconv.FormatUint(delta, 1) + " time(s)",
		Labels:    map[string]string{"count": strconv.FormatUint(delta, 1)},
	}
	ec.pushEvent(evt)
}

// StartDockerListener starts listening for Docker container events in background
func (ec *EventCollector) StartDockerListener(ctx context.Context) {
	if !ec.dockerAvailable {
		return
	}
	go ec.listenDockerEvents(ctx)
}

func (ec *EventCollector) listenDockerEvents(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		default:
		}

		cli, err := client.NewClientWithOpts(client.WithAPIVersionNegotiation())
		if err != nil {
			log.Printf("WARN: docker client error: %v, retrying in 30s", err)
			time.Sleep(30 * time.Second)
			continue
		}

		f := filters.NewArgs(
			filters.Arg("type", "container"),
			filters.Arg("event", "die"),
			filters.Arg("event", "oom"),
			filters.Arg("event", "kill"),
		)

		msgCh, errCh := cli.Events(ctx, types.EventsOptions{Filters: f})

		log.Println("Docker event listener started")
		ec.handleDockerEventStream(ctx, msgCh, errCh, cli)
		cli.Close()

		// Reconnect after error
		select {
		case <-ctx.Done():
			return
		case <-time.After(5 * time.Second):
		}
	}
}

func (ec *EventCollector) handleDockerEventStream(
	ctx context.Context,
	msgCh <-chan events.Message,
	errCh <-chan error,
	cli *client.Client,
) {
	for {
		select {
		case <-ctx.Done():
			return
		case msg, ok := <-msgCh:
			if !ok {
				return
			}
			ec.processDockerEvent(msg)
		case err, ok := <-errCh:
			if !ok {
				return
			}
			log.Printf("WARN: docker events error: %v", err)
			return
		}
	}
}

func (ec *EventCollector) processDockerEvent(msg events.Message) {
	containerName := msg.Actor.Attributes["name"]
	exitCode := msg.Actor.Attributes["exitCode"]
	action := string(msg.Action)

	var severity, title string
	switch action {
	case "oom":
		severity = "critical"
		title = "Container OOM: " + containerName
	case "die":
		severity = "warning"
		if exitCode == "0" {
			severity = "info"
		}
		title = "Container exited: " + containerName + " (code " + exitCode + ")"
	case "kill":
		severity = "warning"
		title = "Container killed: " + containerName
	default:
		return
	}

	detail := "Container: " + containerName +
		"\nAction: " + action +
		"\nImage: " + msg.Actor.Attributes["image"] +
		"\nExit Code: " + exitCode

	evt := &SystemEvent{
		Timestamp: time.Unix(msg.Time, 0),
		Category:  "container",
		Severity:  severity,
		Source:    "docker",
		Title:     title,
		Detail:    detail,
		Labels: map[string]string{
			"container": containerName,
			"action":    action,
			"exit_code": exitCode,
			"image":     msg.Actor.Attributes["image"],
		},
	}
	ec.pushEvent(evt)
}

// DrainEvents returns all buffered events and clears the buffer
func (ec *EventCollector) DrainEvents() []*SystemEvent {
	ec.mu.Lock()
	defer ec.mu.Unlock()
	if len(ec.events) == 0 {
		return nil
	}
	events := ec.events
	ec.events = nil
	return events
}

func (ec *EventCollector) pushEvent(evt *SystemEvent) {
	ec.mu.Lock()
	defer ec.mu.Unlock()

	// Dedup: same title within dedup window
	if last, ok := ec.recentTitles[evt.Title]; ok && time.Since(last) < ec.dedupWindow {
		return
	}
	ec.recentTitles[evt.Title] = time.Now()

	// Clean old dedup entries
	for t, ts := range ec.recentTitles {
		if time.Since(ts) > ec.dedupWindow {
			delete(ec.recentTitles, t)
		}
	}

	// Rate limit
	if len(ec.events) >= ec.maxEvents {
		ec.events = ec.events[1:]
		log.Printf("WARN: event buffer full, dropping oldest event")
	}

	ec.events = append(ec.events, evt)
	log.Printf("EVENT: [%s] %s %s", evt.Severity, evt.Category, evt.Title)
}

// readOOMKillCount reads oom_kill count from /proc/vmstat
func readOOMKillCount() uint64 {
	f, err := os.Open("/proc/vmstat")
	if err != nil {
		return 0
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "oom_kill ") {
			parts := strings.Fields(line)
			if len(parts) >= 2 {
				val, err := strconv.ParseUint(parts[1], 10, 64)
				if err == nil {
					return val
				}
			}
		}
	}
	return 0
}
