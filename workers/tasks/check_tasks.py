"""
S-02: Operational Check Celery Tasks — daily/hourly read-only wrappers

이 모듈은 기존 운영 점검 러너를 Celery task로 감싸는 wrapper만 제공한다.
read-only 점검만 수행하며 write/destructive action은 포함하지 않는다.

러너: app.core.constitution_check_runner (I-03)
원칙: Check, Don't Repair (제24조)
"""

from workers.celery_app import celery_app


@celery_app.task(name="workers.tasks.check_tasks.run_daily_ops_check")
def run_daily_ops_check():
    """
    S-02: Daily operational check wrapper.
    Calls I-03 run_daily_check(). Read-only. No write action.
    """
    try:
        from app.core.constitution_check_runner import run_daily_check

        result = run_daily_check()
        return {
            "check_type": "DAILY",
            "result": result.result.value,
            "summary": result.summary,
            "items_total": len(result.items),
            "items_passed": sum(1 for i in result.items if i.grade.value == "OK"),
            "evidence_id": result.evidence_id,
            "failures": result.failures[:5],
        }
    except Exception as e:
        return {
            "check_type": "DAILY",
            "result": "FAIL",
            "summary": f"Daily check task failed: {e}",
            "error": str(e),
        }


@celery_app.task(name="workers.tasks.check_tasks.run_hourly_ops_check")
def run_hourly_ops_check():
    """
    S-02: Hourly operational check wrapper.
    Calls I-03 run_hourly_check(). Read-only. No write action.
    """
    try:
        from app.core.constitution_check_runner import run_hourly_check

        result = run_hourly_check()
        return {
            "check_type": "HOURLY",
            "result": result.result.value,
            "summary": result.summary,
            "items_total": len(result.items),
            "items_passed": sum(1 for i in result.items if i.grade.value == "OK"),
            "evidence_id": result.evidence_id,
            "failures": result.failures[:5],
        }
    except Exception as e:
        return {
            "check_type": "HOURLY",
            "result": "FAIL",
            "summary": f"Hourly check task failed: {e}",
            "error": str(e),
        }
