"""
G-MON Tasks: Governance Monitor Celery Tasks — Daily/Weekly automated reports

Daily:  6-indicator OK/WARN/FAIL snapshot + notification on WARN/FAIL
Weekly: 7-day trend summary (aggregated from daily results)

Read-only. No auto-repair. Check, Don't Repair (Art24).
"""

from workers.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(name="workers.tasks.governance_monitor_tasks.run_daily_governance_report")
def run_daily_governance_report():
    """
    G-MON: Daily governance monitor report.
    Collects 6 indicators, formats report, sends notification if WARN/FAIL.
    """
    try:
        from app.core.governance_monitor import (
            run_governance_monitor,
            format_report_text,
            format_discord_report,
            IndicatorStatus,
        )

        report = run_governance_monitor()
        text = format_report_text(report)
        logger.info("governance_monitor_daily", overall=report.overall.value, summary=report.summary)

        # Persist to file (append JSONL)
        _append_report_file(report)

        # Send notification if not all OK
        if report.overall != IndicatorStatus.OK:
            _send_notification(report)

        return report.to_dict()

    except Exception as e:
        logger.error("governance_monitor_daily_failed", error=str(e))
        return {
            "check_type": "GOVERNANCE_DAILY",
            "result": "FAIL",
            "summary": f"Governance monitor task failed: {e}",
            "error": str(e),
        }


@celery_app.task(name="workers.tasks.governance_monitor_tasks.run_weekly_governance_summary")
def run_weekly_governance_summary():
    """
    G-MON: Weekly governance trend summary.
    Reads daily reports from JSONL file and produces 7-day trend analysis.
    """
    try:
        import json
        from datetime import datetime, timezone, timedelta
        from pathlib import Path

        report_path = Path("data/governance_reports.jsonl")
        if not report_path.exists():
            return {
                "check_type": "GOVERNANCE_WEEKLY",
                "result": "OK",
                "summary": "No daily reports found yet",
            }

        # Read last 7 days of reports
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        reports = []
        for line in report_path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                ts = entry.get("timestamp", "")
                if ts >= cutoff.isoformat():
                    reports.append(entry)
            except json.JSONDecodeError:
                continue

        if not reports:
            return {
                "check_type": "GOVERNANCE_WEEKLY",
                "result": "OK",
                "summary": "No reports in last 7 days",
            }

        # Aggregate
        total = len(reports)
        ok_count = sum(1 for r in reports if r.get("overall") == "OK")
        warn_count = sum(1 for r in reports if r.get("overall") == "WARN")
        fail_count = sum(1 for r in reports if r.get("overall") == "FAIL")

        # Per-indicator trend
        indicator_stats = {}
        for r in reports:
            for ind in r.get("indicators", []):
                name = ind["name"]
                if name not in indicator_stats:
                    indicator_stats[name] = {"OK": 0, "WARN": 0, "FAIL": 0}
                indicator_stats[name][ind["status"]] = indicator_stats[name].get(ind["status"], 0) + 1

        # Determine weekly overall
        if fail_count > 0:
            weekly_overall = "FAIL"
        elif warn_count > 0:
            weekly_overall = "WARN"
        else:
            weekly_overall = "OK"

        summary = (
            f"WEEKLY: {total} reports — {ok_count} OK, {warn_count} WARN, {fail_count} FAIL"
        )

        result = {
            "check_type": "GOVERNANCE_WEEKLY",
            "result": weekly_overall,
            "summary": summary,
            "period_days": 7,
            "total_reports": total,
            "ok_count": ok_count,
            "warn_count": warn_count,
            "fail_count": fail_count,
            "indicator_trends": indicator_stats,
        }

        logger.info("governance_monitor_weekly", overall=weekly_overall, summary=summary)

        # Send weekly notification if any issues
        if weekly_overall != "OK":
            _send_weekly_notification(result)

        return result

    except Exception as e:
        logger.error("governance_monitor_weekly_failed", error=str(e))
        return {
            "check_type": "GOVERNANCE_WEEKLY",
            "result": "FAIL",
            "summary": f"Weekly summary failed: {e}",
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _append_report_file(report):
    """Append report to JSONL file. Fail-silent."""
    try:
        import json
        from pathlib import Path
        path = Path("data/governance_reports.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(report.to_dict(), ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        logger.warning("governance_report_file_append_failed", error=str(e))


def _send_notification(report):
    """Send governance alert via configured channels. Fail-silent."""
    try:
        from app.core.config import settings
        from app.core.governance_monitor import format_discord_report

        # Discord/webhook notification
        webhook_url = settings.notifier_webhook_url
        if webhook_url:
            from app.core.real_notifier_adapter import send_webhook
            payload = format_discord_report(report)
            send_webhook(webhook_url, payload)

        # File notification
        file_path = settings.notifier_file_path
        if file_path:
            import json
            from pathlib import Path
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "type": "governance_monitor",
                    "overall": report.overall.value,
                    "summary": report.summary,
                    "timestamp": report.timestamp,
                }, ensure_ascii=False, default=str) + "\n")

    except Exception as e:
        logger.warning("governance_notification_failed", error=str(e))


def _send_weekly_notification(result: dict):
    """Send weekly summary notification. Fail-silent."""
    try:
        from app.core.config import settings
        webhook_url = settings.notifier_webhook_url
        if not webhook_url:
            return

        from app.core.real_notifier_adapter import send_webhook

        overall = result.get("result", "UNKNOWN")
        icon = {"OK": ":white_check_mark:", "WARN": ":warning:", "FAIL": ":x:"}.get(overall, ":grey_question:")

        payload = {
            "content": "\n".join([
                f"{icon} **K-Dexter Weekly Governance Summary** | {overall}",
                f"Period: 7 days | Reports: {result.get('total_reports', 0)}",
                f"OK: {result.get('ok_count', 0)} | WARN: {result.get('warn_count', 0)} | FAIL: {result.get('fail_count', 0)}",
                "",
                f"_{result.get('summary', '')}_",
            ]),
        }
        send_webhook(webhook_url, payload)

    except Exception as e:
        logger.warning("governance_weekly_notification_failed", error=str(e))
