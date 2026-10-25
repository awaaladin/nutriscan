"""Turns a user's logged readings into numbers the app shows and text the AI reads.

Targets are the general ones published guidelines give most adults; the app says so and tells
users their own doctor's targets come first:
  - blood glucose (American Diabetes Association): 80-130 mg/dL fasting or before a meal,
    under 180 mg/dL 1-2 hours after one; under 70 is low; 300 or more needs medical advice;
  - blood pressure (ADA / American Heart Association): under 130/80; 180/120 or more is a crisis;
  - weight: BMI 18.5-24.9 is the WHO healthy range.
"""
from datetime import timedelta
from decimal import Decimal
from typing import List, Optional

from django.utils import timezone

from .models import HealthLog

GLUCOSE_TARGETS = {"fasting": (80, 130), "before_meal": (80, 130), "after_meal": (None, 180), "random": (None, 180)}
GLUCOSE_LOW, GLUCOSE_VERY_HIGH = 70, 300
BP_TARGET = (130, 80)
BP_CRISIS = (180, 120)

URGENT = "Seek medical help now (call 112 or go to the nearest hospital) if you also feel unwell."


def glucose_in_range(log: HealthLog) -> bool:
    low, high = GLUCOSE_TARGETS.get(log.timing or "random", (None, 180))
    value = float(log.value)
    return (low is None or value >= low) and value < high


def bp_in_range(log: HealthLog) -> bool:
    return log.systolic < BP_TARGET[0] and log.diastolic < BP_TARGET[1]


def alert_for(log: HealthLog) -> Optional[str]:
    """A warning for a reading that needs attention now, or None."""
    if log.kind == HealthLog.Kind.GLUCOSE and log.value is not None:
        if log.value < GLUCOSE_LOW:
            return f"{log.value} mg/dL is low blood sugar. Take something sugary now and recheck in 15 minutes. {URGENT}"
        if log.value >= GLUCOSE_VERY_HIGH:
            return f"{log.value} mg/dL is very high. Contact your doctor today. {URGENT}"
    if log.kind == HealthLog.Kind.BLOOD_PRESSURE and log.systolic:
        if log.systolic >= BP_CRISIS[0] or log.diastolic >= BP_CRISIS[1]:
            return f"{log.systolic}/{log.diastolic} is dangerously high. Rest and measure again in 5 minutes. {URGENT}"
    return None


def _avg(values: List[float]) -> Optional[float]:
    return round(sum(values) / len(values), 1) if values else None


def bmi(user, weight_kg) -> Optional[float]:
    if not user.height_cm or weight_kg is None:
        return None
    metres = user.height_cm / 100
    return round(float(weight_kg) / (metres * metres), 1)


def summarize(user, days: int = 30) -> dict:
    since = timezone.now() - timedelta(days=days)
    week = timezone.now() - timedelta(days=7)
    logs = list(HealthLog.objects.filter(user=user, measured_at__gte=since).order_by("measured_at"))
    out = {"days": days}

    weights = [l for l in logs if l.kind == HealthLog.Kind.WEIGHT and l.value is not None]
    if weights:
        latest = weights[-1].value
        out["weight"] = {
            "count": len(weights),
            "latest_kg": float(latest),
            "change_kg": round(float(latest - weights[0].value), 1),
            "bmi": bmi(user, latest),
            "target_kg": float(user.target_weight_kg) if user.target_weight_kg else None,
            "to_target_kg": round(float(latest - user.target_weight_kg), 1) if user.target_weight_kg else None,
        }

    pressures = [l for l in logs if l.kind == HealthLog.Kind.BLOOD_PRESSURE and l.systolic]
    if pressures:
        recent = [l for l in pressures if l.measured_at >= week] or pressures[-3:]
        out["blood_pressure"] = {
            "count": len(pressures),
            "latest": f"{pressures[-1].systolic}/{pressures[-1].diastolic}",
            "avg_7d": f"{_avg([l.systolic for l in recent]):.0f}/{_avg([l.diastolic for l in recent]):.0f}",
            "in_target_pct": round(100 * sum(bp_in_range(l) for l in pressures) / len(pressures)),
            "target": f"under {BP_TARGET[0]}/{BP_TARGET[1]}",
        }

    glucose = [l for l in logs if l.kind == HealthLog.Kind.GLUCOSE and l.value is not None]
    if glucose:
        fasting = [float(l.value) for l in glucose if l.timing in ("fasting", "before_meal")]
        after = [float(l.value) for l in glucose if l.timing == "after_meal"]
        out["glucose"] = {
            "count": len(glucose),
            "latest_mg_dl": float(glucose[-1].value),
            "latest_timing": glucose[-1].get_timing_display() if glucose[-1].timing else "",
            "avg_fasting_mg_dl": _avg(fasting),
            "avg_after_meal_mg_dl": _avg(after),
            "in_target_pct": round(100 * sum(glucose_in_range(l) for l in glucose) / len(glucose)),
            "lows": sum(1 for l in glucose if l.value < GLUCOSE_LOW),
            "target": "80-130 mg/dL fasting, under 180 mg/dL after meals",
        }

    out["alerts"] = [a for a in (alert_for(l) for l in logs if l.measured_at >= week) if a][-3:]
    return out


def readings_context(user) -> List[str]:
    """Lines for the AI's OUR DATA section: the user's own recent readings, if any."""
    s = summarize(user)
    lines = []
    if "weight" in s:
        w = s["weight"]
        lines.append(
            f"- Weight: {w['latest_kg']} kg (changed {w['change_kg']:+} kg in 30 days)"
            + (f", BMI {w['bmi']}" if w["bmi"] else "")
            + (f", goal {w['target_kg']} kg" if w["target_kg"] else "")
        )
    if "blood_pressure" in s:
        b = s["blood_pressure"]
        lines.append(f"- Blood pressure: latest {b['latest']}, 7-day average {b['avg_7d']}, {b['in_target_pct']}% of readings under 130/80")
    if "glucose" in s:
        g = s["glucose"]
        parts = [f"latest {g['latest_mg_dl']} mg/dL" + (f" ({g['latest_timing'].lower()})" if g["latest_timing"] else "")]
        if g["avg_fasting_mg_dl"]:
            parts.append(f"average fasting {g['avg_fasting_mg_dl']}")
        if g["avg_after_meal_mg_dl"]:
            parts.append(f"average after meals {g['avg_after_meal_mg_dl']}")
        parts.append(f"{g['in_target_pct']}% in target, {g['lows']} low reading(s)")
        lines.append("- Blood glucose (30 days): " + ", ".join(parts))
    return lines
