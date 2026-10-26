// Command ordersvc starts the order service.
package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"example.com/ordersvc/internal/config"
	"example.com/ordersvc/internal/httpapi"
	"example.com/ordersvc/internal/order"
)

func main() {
	if err := run(); err != nil {
		slog.Error("ordersvc exited", "err", err)
		os.Exit(1)
	}
}

// run owns wiring and the process lifecycle; everything below it is testable.
func run() error {
	cfg, err := config.Load(os.Getenv("ORDERSVC_CONFIG"))
	if err != nil {
		return err
	}

	svc := order.NewService(order.NewMemoryRepository())
	srv := &http.Server{
		Addr:              cfg.Addr,
		Handler:           httpapi.NewRouter(svc),
		ReadHeaderTimeout: 5 * time.Second,
	}

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	errc := make(chan error, 1)
	go func() {
		errc <- srv.ListenAndServe()
	}()

	select {
	case err := <-errc:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	case <-ctx.Done():
	}

	shutdownCtx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownTimeout)
	defer cancel()
	return srv.Shutdown(shutdownCtx)
}
