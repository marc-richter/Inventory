from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import APIRouter, Response, Depends
from sqlalchemy.orm import Session

from app import security
from app.database import get_db
from app import models


router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])

# HTTP metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
)

# Business metrics
articles_total = Gauge("articles_total", "Total number of articles")
articles_by_status = Gauge("articles_by_status", "Articles grouped by status", ["status"])
users_total = Gauge("users_total", "Total number of users")
active_users = Gauge("active_users", "Active users in last 5 minutes")
inventory_campaigns_active = Gauge("inventory_campaigns_active", "Active inventory campaigns")
open_issues = Gauge("open_issues", "Currently open issues (issued articles not returned)")
low_stock_alerts = Gauge("low_stock_alerts", "Number of items below minimum stock")

# Database metrics
db_connections = Gauge("db_connections_active", "Active database connections")


@router.get("")
async def metrics(
    response: Response,
    user=Depends(security.require_roles("admin")),
):
    """Prometheus metrics endpoint. Requires admin role."""
    response.headers["Content-Type"] = CONTENT_TYPE_LATEST
    return generate_latest()


@router.get("/business")
def business_metrics(
    db: Session = Depends(get_db),
    user=Depends(security.require_roles("admin")),
):
    """JSON endpoint with current business metrics."""
    articles_total.set(db.query(models.Article).count())
    users_total.set(db.query(models.User).count())

    # Active users (last 5 minutes)
    import datetime as dt
    five_min_ago = dt.datetime.utcnow() - dt.timedelta(minutes=5)
    active_users.set(
        db.query(models.User)
        .filter(models.User.last_seen >= five_min_ago)
        .count()
    )

    # Articles by status
    from sqlalchemy import func
    status_counts = db.query(models.Article.status, func.count(models.Article.id)).group_by(models.Article.status).all()
    for status, count in status_counts:
        articles_by_status.labels(status=status).set(count)

    # Active inventory campaigns
    inventory_campaigns_active.set(
        db.query(models.InventoryCampaign)
        .filter(models.InventoryCampaign.status == "running")
        .count()
    )

    # Open issues
    open_issues.set(
        db.query(models.IssueRecord)
        .filter(models.IssueRecord.return_date.is_(None))
        .count()
    )

    # Low stock alerts (simplified)
    low_stock_alerts.set(
        db.query(models.MinStockRule)
        .filter(models.MinStockRule.min_stock > 0)
        .count()
    )

    return {
        "articles_total": articles_total._value.get(),
        "users_total": users_total._value.get(),
        "active_users": active_users._value.get(),
        "inventory_campaigns_active": inventory_campaigns_active._value.get(),
        "open_issues": open_issues._value.get(),
        "low_stock_alerts": low_stock_alerts._value.get(),
    }