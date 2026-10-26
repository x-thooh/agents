package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadEmptyPathReturnsDefaults(t *testing.T) {
	cfg, err := Load("")
	if err != nil {
		t.Fatalf("Load(\"\"): %v", err)
	}
	if cfg.Addr != Default().Addr {
		t.Fatalf("addr = %q, want %q", cfg.Addr, Default().Addr)
	}
}

func TestLoadValidFile(t *testing.T) {
	path := writeFixture(t, `{"addr":":9090"}`)
	cfg, err := Load(path)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if cfg.Addr != ":9090" {
		t.Fatalf("addr = %q, want :9090", cfg.Addr)
	}
}

func TestLoadRejectsInvalidJSON(t *testing.T) {
	if _, err := Load(writeFixture(t, "{")); err == nil {
		t.Fatal("want error for invalid json, got nil")
	}
}

func TestLoadRejectsEmptyAddr(t *testing.T) {
	if _, err := Load(writeFixture(t, `{"addr":""}`)); err == nil {
		t.Fatal("want error for empty addr, got nil")
	}
}

func writeFixture(t *testing.T, body string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "config.json")
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatalf("write fixture: %v", err)
	}
	return path
}
