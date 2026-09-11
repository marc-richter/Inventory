# Monitoring Setup für Inventarprogramm

## Schnellstart

```bash
# 1. Prometheus + Grafana starten
docker compose -f docker-compose.monitoring.yml up -d

# 2. Grafana öffnen
# http://localhost:3000 (admin / admin1234)

# 3. Prometheus öffnen
# http://localhost:9090
```

## Dashboards

Das Dashboard `inventarprogramm-dashboard.json` wird automatisch in Grafana geladen (Provisioning). Es enthält:

- **HTTP Metriken**: Request Rate, Success Rate, Latency (p50/p95)
- **Business Metriken**: Articles, Users, Open Issues, Low Stock, Active Campaigns
- **System Metriken**: Active Users (5min), Articles by Status

## Prometheus Metriken

Verfügbare Endpunkte:

| Endpoint | Beschreibung |
|----------|-------------|
| `/api/v1/metrics` | Prometheus-Format (alle Metriken) |
| `/api/v1/metrics/business` | JSON mit aktuellen Business-Metriken |

Wichtige Metriken:

| Metrik | Typ | Beschreibung |
|--------|-----|-------------|
| `http_requests_total` | Counter | HTTP Requests nach Method/Endpoint/Status |
| `http_request_duration_seconds` | Histogram | Request-Latenz |
| `articles_total` | Gauge | Gesamtzahl Artikel |
| `articles_by_status` | Gauge | Artikel gruppiert nach Status |
| `users_total` | Gauge | Gesamtzahl Benutzer |
| `active_users` | Gauge | Aktive Nutzer (letzte 5 Min) |
| `open_issues` | Gauge | Offene Ausgaben |
| `low_stock_alerts` | Gauge | Mindestbestands-Unterschreitungen |
| `inventory_campaigns_active` | Gauge | Laufende Inventur-Kampagnen |

## Grafana Dashboard importieren

Das Dashboard wird automatisch provisioned. Falls manuell:

1. Grafana öffnen → Dashboards → Import
2. JSON-Datei `monitoring/grafana/inventarprogramm-dashboard.json` hochladen
3. Prometheus als Datasource wählen

## Alerting (optional)

Beispiel Alert-Regeln für Prometheus (`alerts.yml`):

```yaml
groups:
  - name: inventarprogramm
    rules:
      - alert: HighErrorRate
        expr: sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Hohe Fehlerrate (>5%)"

      - alert: LowStockAlert
        expr: low_stock_alerts > 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Mindestbestand unterschritten"

      - alert: HighLatency
        expr: histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint)) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Hohe Latenz (p95 > 2s)"
```

## Passwörter ändern

```bash
# .env Datei für Monitoring
cat > .env.monitoring <<EOF
INVENTAR_ADMIN_PASSWORD=your-secure-password
GRAFANA_ADMIN_PASSWORD=your-secure-password
EOF

docker compose -f docker-compose.monitoring.yml --env-file .env.monitoring up -d
```

## Netzwerk

Das Monitoring nutzt das externe Netzwerk `inventar-network`. Stellen Sie sicher, dass es existiert:

```bash
docker network create inventar-network
```

## Logs prüfen

```bash
# Prometheus
docker logs inventar-prometheus

# Grafana
docker logs inventar-grafana
```