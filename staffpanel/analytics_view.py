"""The staff Analytics page: real website visits, drawn as charts (inline SVG, no JavaScript needed)."""
from collections import Counter
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.db.models.functions import TruncDate, TruncHour
from django.shortcuts import render
from django.utils import timezone

from .access import staff_required
from .models import PageView

User = get_user_model()


def _nice_max(value):
    """Round a chart's top up to a tidy number so the grid lines read well."""
    if value <= 4:
        return 4
    step = 10 ** (len(str(int(value))) - 1)
    for mult in (1, 2, 2.5, 5, 10):
        if step * mult >= value:
            return int(step * mult)
    return int(step * 10)


def line_chart(labels, series, width=760, height=240):
    """An SVG line chart from real numbers. series = [{name, color, values}]."""
    left, right, top, bottom = 38, 12, 14, 26
    inner_w, inner_h = width - left - right, height - top - bottom
    peak = _nice_max(max([max(s["values"]) for s in series if s["values"]] + [1]))
    n = max(len(labels), 2)

    def x(i):
        return left + inner_w * i / (n - 1)

    def y(v):
        return top + inner_h * (1 - v / peak)

    grid = [{"y": round(y(peak * k / 4), 1), "label": int(peak * k / 4)} for k in range(5)]
    step = max(1, len(labels) // 6)
    ticks = [{"x": round(x(i), 1), "label": labels[i]} for i in range(0, len(labels), step)]
    lines = []
    for s in series:
        points = [(round(x(i), 1), round(y(v), 1)) for i, v in enumerate(s["values"])]
        path = "M" + " L".join(f"{px},{py}" for px, py in points)
        base = round(y(0), 1)
        area = f"{path} L{points[-1][0]},{base} L{points[0][0]},{base} Z" if points else ""
        lines.append({
            "name": s["name"], "color": s["color"], "path": path, "area": area,
            "dots": [{"x": px, "y": py, "tip": f"{labels[i]}: {s['values'][i]} {s['name'].lower()}"} for i, (px, py) in enumerate(points)],
        })
    return {"width": width, "height": height, "grid": grid, "ticks": ticks, "lines": lines, "left": left, "right": width - right}


@staff_required
def analytics(request):
    try:
        days = int(request.GET.get("days", 30))
    except ValueError:
        days = 30
    days = days if days in (7, 30, 90) else 30
    now = timezone.now()
    today = timezone.localdate()
    first_day = today - timedelta(days=days - 1)
    since = timezone.make_aware(datetime.combine(first_day, datetime.min.time()))
    views = PageView.objects.filter(at__gte=since)

    def per_day(qs, field, **count):
        return {r["d"]: r["n"] for r in qs.annotate(d=TruncDate(field)).values("d").annotate(n=Count("id", **count))}

    day_views = per_day(views, "at")
    day_visitors = {r["d"]: r["n"] for r in views.annotate(d=TruncDate("at")).values("d").annotate(n=Count("visitor", distinct=True))}
    day_signups = per_day(User.objects.filter(date_joined__gte=since), "date_joined")
    dates = [first_day + timedelta(days=i) for i in range(days)]
    labels = [f"{d.day} {d:%b}" for d in dates]
    chart = line_chart(labels, [
        {"name": "Page views", "color": "#12a58a", "values": [day_views.get(d, 0) for d in dates]},
        {"name": "Visitors", "color": "#2f6bd6", "values": [day_visitors.get(d, 0) for d in dates]},
    ])
    signup_chart = line_chart(labels, [{"name": "New accounts", "color": "#7c3aed", "values": [day_signups.get(d, 0) for d in dates]}], height=170)

    visitors = views.values("visitor").distinct().count()
    total_views = views.count()
    days_seen = Counter(r["visitor"] for r in views.annotate(d=TruncDate("at")).values("visitor", "d").distinct())
    returning = sum(1 for v in days_seen.values() if v > 1)

    def top(field, limit, blank="Direct"):
        rows = list(views.values(field).annotate(n=Count("id"), people=Count("visitor", distinct=True)).order_by("-n")[:limit])
        peak = max([r["n"] for r in rows] + [1])
        return [{"name": r[field] or blank, "n": r["n"], "people": r["people"], "pct": round(100 * r["n"] / peak)} for r in rows]

    hourly = {r["h"]: r["n"] for r in PageView.objects.filter(at__gte=now - timedelta(hours=24)).annotate(h=TruncHour("at")).values("h").annotate(n=Count("id"))}
    start_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=23)
    hour_rows = []
    for i in range(24):
        moment = start_hour + timedelta(hours=i)
        hour_rows.append({"label": timezone.localtime(moment).strftime("%H:00"), "n": hourly.get(moment, 0)})
    hour_peak = max([h["n"] for h in hour_rows] + [1])
    for h in hour_rows:
        h["pct"] = round(100 * h["n"] / hour_peak)

    context = {
        "nav": "analytics", "days": days, "chart": chart, "signup_chart": signup_chart, "hour_rows": hour_rows, "hour_peak": hour_peak,
        "visitors": visitors, "views": total_views, "per_visitor": round(total_views / visitors, 1) if visitors else 0,
        "returning_pct": round(100 * returning / visitors) if visitors else 0,
        "signups": sum(day_signups.values()),
        "live": PageView.objects.filter(at__gte=now - timedelta(minutes=5)).values("visitor").distinct().count(),
        "today_visitors": day_visitors.get(today, 0),
        "pages": top("path", 10), "sources": top("referrer", 8), "devices": top("device", 3, "Unknown"), "countries": top("country", 8, "Unknown"),
        "counting_since": PageView.objects.order_by("at").values_list("at", flat=True).first(), "has_data": total_views > 0,
    }
    return render(request, "staff/analytics.html", context)
