// Package order implements order creation and lookup.
package order

import (
	"errors"
	"fmt"
	"sync"
	"time"
)

// ErrNotFound reports a missing order.
var ErrNotFound = errors.New("order not found")

// Status is the lifecycle state of an order.
type Status string

const (
	// StatusNew marks an order that has been accepted but not paid.
	StatusNew Status = "new"
	// StatusPaid marks an order whose payment has settled.
	StatusPaid Status = "paid"
)

// Order is a customer order.
type Order struct {
	ID        string
	Amount    int64
	Status    Status
	CreatedAt time.Time
}

// Repository stores orders.
type Repository interface {
	Save(Order) error
	Get(string) (Order, error)
}

// MemoryRepository is an in-process Repository for tests and local runs.
type MemoryRepository struct {
	mu     sync.RWMutex
	orders map[string]Order
}

// NewMemoryRepository returns an empty MemoryRepository.
func NewMemoryRepository() *MemoryRepository {
	return &MemoryRepository{orders: make(map[string]Order)}
}

// Save stores o, replacing any previous value with the same ID.
func (r *MemoryRepository) Save(o Order) error {
	if o.ID == "" {
		return fmt.Errorf("save order: empty id")
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	r.orders[o.ID] = o
	return nil
}

// Get returns the order with the given id, or ErrNotFound.
func (r *MemoryRepository) Get(id string) (Order, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	o, ok := r.orders[id]
	if !ok {
		return Order{}, fmt.Errorf("get order %q: %w", id, ErrNotFound)
	}
	return o, nil
}
