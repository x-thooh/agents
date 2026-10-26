package httpapi

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"example.com/ordersvc/internal/order"
)

func newTestRouter() http.Handler {
	return NewRouter(order.NewService(order.NewMemoryRepository()))
}

func do(t *testing.T, method, target, body string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(method, target, strings.NewReader(body))
	rec := httptest.NewRecorder()
	newTestRouter().ServeHTTP(rec, req)
	return rec
}

func TestCreateOrder(t *testing.T) {
	rec := do(t, http.MethodPost, "/orders", `{"id":"o-1","amount":100}`)
	if rec.Code != http.StatusCreated {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusCreated)
	}
}

func TestCreateOrderInvalidJSON(t *testing.T) {
	rec := do(t, http.MethodPost, "/orders", `{`)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusBadRequest)
	}
}

func TestCreateOrderRejectsGet(t *testing.T) {
	rec := do(t, http.MethodGet, "/orders", "")
	if rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusMethodNotAllowed)
	}
}

func TestGetOrderNotFound(t *testing.T) {
	rec := do(t, http.MethodGet, "/orders/missing", "")
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusNotFound)
	}
}

func TestGetOrderMissingID(t *testing.T) {
	rec := do(t, http.MethodGet, "/orders/", "")
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want %d", rec.Code, http.StatusBadRequest)
	}
}
