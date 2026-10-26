package order

import (
	"context"
	"errors"
	"fmt"
	"time"
)

// ErrInvalidAmount reports a non-positive order amount.
var ErrInvalidAmount = errors.New("invalid amount")

// Service applies order use cases on top of a Repository.
type Service struct {
	repo Repository
	now  func() time.Time
}

// NewService wires a Service around repo.
func NewService(repo Repository) *Service {
	return &Service{repo: repo, now: time.Now}
}

// Create validates and stores a new order.
func (s *Service) Create(ctx context.Context, id string, amount int64) (Order, error) {
	if err := ctx.Err(); err != nil {
		return Order{}, fmt.Errorf("create order %q: %w", id, err)
	}
	if amount <= 0 {
		return Order{}, fmt.Errorf("create order %q: %w", id, ErrInvalidAmount)
	}
	o := Order{ID: id, Amount: amount, Status: StatusNew, CreatedAt: s.now()}
	if err := s.repo.Save(o); err != nil {
		return Order{}, fmt.Errorf("create order %q: %w", id, err)
	}
	return o, nil
}

// Get returns the order with the given id, or ErrNotFound.
func (s *Service) Get(ctx context.Context, id string) (Order, error) {
	if err := ctx.Err(); err != nil {
		return Order{}, fmt.Errorf("get order %q: %w", id, err)
	}
	o, err := s.repo.Get(id)
	if err != nil {
		return Order{}, fmt.Errorf("get order %q: %w", id, err)
	}
	return o, nil
}
