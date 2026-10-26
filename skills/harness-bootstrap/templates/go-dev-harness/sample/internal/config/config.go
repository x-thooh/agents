// Package config loads service configuration from a JSON file.
package config

import (
	"encoding/json"
	"fmt"
	"os"
	"time"
)

// Config is the runtime configuration of the order service.
type Config struct {
	Addr            string        `json:"addr"`
	RequestTimeout  time.Duration `json:"-"`
	ShutdownTimeout time.Duration `json:"-"`
}

// Default returns the configuration used when no file is supplied.
func Default() Config {
	return Config{
		Addr:            ":8080",
		RequestTimeout:  3 * time.Second,
		ShutdownTimeout: 10 * time.Second,
	}
}

// Load reads the JSON file at path and validates the result.
// An empty path yields the defaults.
func Load(path string) (Config, error) {
	cfg := Default()
	if path == "" {
		return cfg, nil
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return Config{}, fmt.Errorf("read config %q: %w", path, err)
	}
	if err := json.Unmarshal(raw, &cfg); err != nil {
		return Config{}, fmt.Errorf("decode config %q: %w", path, err)
	}
	if cfg.Addr == "" {
		return Config{}, fmt.Errorf("config %q: addr is empty", path)
	}
	return cfg, nil
}
