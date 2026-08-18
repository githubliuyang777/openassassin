package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"strconv"
)

type Config struct {
	ServerURL string
	Token     string
	Interval  int
	Hostname  string
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func getEnvInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return fallback
}

func parseConfig() *Config {
	cfg := &Config{}

	defaultServer := getEnv("OA_SERVER_URL", "")
	defaultToken := getEnv("OA_HOST_TOKEN", "")
	defaultInterval := getEnvInt("OA_INTERVAL", 30)
	defaultHostname := getEnv("OA_HOSTNAME", "")

	flag.StringVar(&cfg.ServerURL, "server", defaultServer, "Platform server URL")
	flag.StringVar(&cfg.Token, "token", defaultToken, "Host agent token")
	flag.IntVar(&cfg.Interval, "interval", defaultInterval, "Report interval in seconds")
	flag.StringVar(&cfg.Hostname, "hostname", defaultHostname, "Hostname override")
	versionFlag := flag.Bool("version", false, "Print version and exit")
	flag.Parse()

	if *versionFlag {
		fmt.Printf("host-agent v%s\n", Version)
		os.Exit(0)
	}

	if cfg.ServerURL == "" {
		log.Fatal("SERVER_URL is required. Set via --server or OA_SERVER_URL env var")
	}
	if cfg.Token == "" {
		log.Fatal("TOKEN is required. Set via --token or OA_HOST_TOKEN env var")
	}
	if cfg.Interval < 5 {
		log.Fatal("INTERVAL must be at least 5 seconds")
	}

	if cfg.Hostname == "" {
		hostname, err := os.Hostname()
		if err == nil {
			cfg.Hostname = hostname
		} else {
			cfg.Hostname = "unknown"
		}
	}

	// Strip trailing slash from server URL
	for len(cfg.ServerURL) > 0 && cfg.ServerURL[len(cfg.ServerURL)-1] == '/' {
		cfg.ServerURL = cfg.ServerURL[:len(cfg.ServerURL)-1]
	}

	return cfg
}
