// Package httpapi exposes the order service over HTTP.
package httpapi

import (
	"encoding/json"
	"errors"
	"net/http"
	"strings"

	"example.com/ordersvc/internal/order"
)

// NewRouter returns the HTTP handler tree of the service.
func NewRouter(svc *order.Service) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/orders", createOrder(svc))
	mux.HandleFunc("/orders/", getOrder(svc))
	return mux
}

func createOrder(svc *order.Service) http.HandlerFunc {
	type request struct {
		ID     string `json:"id"`
		Amount int64  `json:"amount"`
	}
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			writeError(w, http.StatusMethodNotAllowed, "method not allowed")
			return
		}
		var body request
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			writeError(w, http.StatusBadRequest, "invalid json body")
			return
		}
		created, err := svc.Create(r.Context(), body.ID, body.Amount)
		if err != nil {
			writeError(w, http.StatusBadRequest, err.Error())
			return
		}
		writeJSON(w, http.StatusCreated, created)
	}
}

func getOrder(svc *order.Service) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := strings.TrimPrefix(r.URL.Path, "/orders/")
		if id == "" {
			writeError(w, http.StatusBadRequest, "missing order id")
			return
		}
		found, err := svc.Get(r.Context(), id)
		if errors.Is(err, order.ErrNotFound) {
			writeError(w, http.StatusNotFound, "order not found")
			return
		}
		if err != nil {
			writeError(w, http.StatusInternalServerError, "internal error")
			return
		}
		writeJSON(w, http.StatusOK, found)
	}
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]string{"error": message})
}
