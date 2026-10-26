package order

import (
	"context"
	"errors"
	"testing"
)

func TestServiceCreate(t *testing.T) {
	tests := []struct {
		name    string
		id      string
		amount  int64
		wantErr error
	}{
		{name: "accepted", id: "o-1", amount: 100},
		{name: "zero amount", id: "o-2", amount: 0, wantErr: ErrInvalidAmount},
		{name: "negative amount", id: "o-3", amount: -1, wantErr: ErrInvalidAmount},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			svc := NewService(NewMemoryRepository())
			_, err := svc.Create(context.Background(), tc.id, tc.amount)
			if tc.wantErr == nil {
				if err != nil {
					t.Fatalf("unexpected error: %v", err)
				}
				return
			}
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("err = %v, want %v", err, tc.wantErr)
			}
		})
	}
}

func TestServiceCreateWithCanceledContext(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	svc := NewService(NewMemoryRepository())
	if _, err := svc.Create(ctx, "o-1", 100); !errors.Is(err, context.Canceled) {
		t.Fatalf("err = %v, want context.Canceled", err)
	}
}

func TestServiceGetAfterCreate(t *testing.T) {
	svc := NewService(NewMemoryRepository())
	created, err := svc.Create(context.Background(), "o-1", 100)
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	found, err := svc.Get(context.Background(), created.ID)
	if err != nil {
		t.Fatalf("get: %v", err)
	}
	if found.Amount != created.Amount {
		t.Fatalf("amount = %d, want %d", found.Amount, created.Amount)
	}
}

func TestServiceGetMissing(t *testing.T) {
	svc := NewService(NewMemoryRepository())
	if _, err := svc.Get(context.Background(), "missing"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("err = %v, want ErrNotFound", err)
	}
}

func TestRepositorySaveRejectsEmptyID(t *testing.T) {
	repo := NewMemoryRepository()
	if err := repo.Save(Order{}); err == nil {
		t.Fatal("want error for empty id, got nil")
	}
}

func BenchmarkServiceCreate(b *testing.B) {
	svc := NewService(NewMemoryRepository())
	ctx := context.Background()
	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		if _, err := svc.Create(ctx, "o-bench", 100); err != nil {
			b.Fatalf("create: %v", err)
		}
	}
}
