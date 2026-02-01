"""Schedule calculation utilities.

Computes next run times for different schedule types using croniter for cron expressions.
"""
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from .types import (
    Schedule,
    AtSchedule,
    EverySchedule,
    CronSchedule,
)


def now_ms() -> int:
    """Get current timestamp in milliseconds."""
    return int(time.time() * 1000)


def compute_next_run_at_ms(
    schedule: Schedule,
    current_ms: int | None = None,
    last_run_at_ms: int | None = None,
) -> int | None:
    """Compute the next run time in milliseconds.

    Args:
        schedule: The schedule configuration
        current_ms: Current timestamp in ms (defaults to now)
        last_run_at_ms: Last run timestamp in ms (for interval schedules)

    Returns:
        Next run timestamp in milliseconds, or None if no more runs
    """
    if current_ms is None:
        current_ms = now_ms()

    if isinstance(schedule, AtSchedule):
        return _compute_at_next(schedule, current_ms)
    elif isinstance(schedule, EverySchedule):
        return _compute_every_next(schedule, current_ms, last_run_at_ms)
    elif isinstance(schedule, CronSchedule):
        return _compute_cron_next(schedule, current_ms)
    else:
        return None


def _compute_at_next(schedule: AtSchedule, current_ms: int) -> int | None:
    """Compute next run for at (one-time) schedule."""
    # One-time schedule: return the target time if it's in the future
    if schedule.at_ms > current_ms:
        return schedule.at_ms
    return None  # Already passed


def _compute_every_next(
    schedule: EverySchedule,
    current_ms: int,
    last_run_at_ms: int | None,
) -> int | None:
    """Compute next run for interval schedule."""
    if schedule.interval_ms <= 0:
        return None

    if last_run_at_ms is None:
        # First run: schedule immediately or at next interval
        return current_ms + schedule.interval_ms

    # Calculate next run based on last run
    next_run = last_run_at_ms + schedule.interval_ms

    # If we're past the next run, align to future
    while next_run <= current_ms:
        next_run += schedule.interval_ms

    return next_run


def _compute_cron_next(schedule: CronSchedule, current_ms: int) -> int | None:
    """Compute next run for cron schedule using croniter."""
    try:
        from croniter import croniter
    except ImportError:
        # Fallback: try to parse common patterns manually
        return _compute_cron_fallback(schedule, current_ms)

    try:
        # Convert ms to datetime in the specified timezone
        tz = ZoneInfo(schedule.timezone)
        current_dt = datetime.fromtimestamp(current_ms / 1000, tz=tz)

        # Create croniter instance
        cron = croniter(schedule.expression, current_dt)

        # Get next run time
        next_dt = cron.get_next(datetime)

        # Convert back to milliseconds
        return int(next_dt.timestamp() * 1000)

    except Exception:
        return _compute_cron_fallback(schedule, current_ms)


def _compute_cron_fallback(schedule: CronSchedule, current_ms: int) -> int | None:
    """Fallback cron calculation for simple patterns when croniter is unavailable."""
    # Parse the expression
    parts = schedule.expression.split()
    if len(parts) != 5:
        return None

    minute, hour, day, month, weekday = parts

    try:
        tz = ZoneInfo(schedule.timezone)
        current_dt = datetime.fromtimestamp(current_ms / 1000, tz=tz)

        # Handle simple daily patterns: "0 9 * * *" (every day at 9:00)
        if day == "*" and month == "*" and weekday == "*":
            if minute.isdigit() and hour.isdigit():
                target_minute = int(minute)
                target_hour = int(hour)

                # Calculate next occurrence
                next_dt = current_dt.replace(
                    hour=target_hour,
                    minute=target_minute,
                    second=0,
                    microsecond=0,
                )

                # If past today's time, schedule for tomorrow
                if next_dt <= current_dt:
                    next_dt = next_dt.replace(day=next_dt.day + 1)

                return int(next_dt.timestamp() * 1000)

        # Handle interval patterns: "*/30 * * * *" (every 30 minutes)
        if minute.startswith("*/") and hour == "*" and day == "*" and month == "*" and weekday == "*":
            interval_minutes = int(minute[2:])
            current_minute = current_dt.minute

            # Find next aligned minute
            next_minute = ((current_minute // interval_minutes) + 1) * interval_minutes
            if next_minute >= 60:
                next_dt = current_dt.replace(minute=next_minute % 60, second=0, microsecond=0)
                next_dt = next_dt.replace(hour=next_dt.hour + 1)
            else:
                next_dt = current_dt.replace(minute=next_minute, second=0, microsecond=0)

            return int(next_dt.timestamp() * 1000)

    except Exception:
        pass

    # Unable to compute
    return None


def validate_cron_expression(expression: str) -> bool:
    """Validate a cron expression.

    Args:
        expression: Cron expression to validate

    Returns:
        True if valid, False otherwise
    """
    parts = expression.split()
    if len(parts) != 5:
        return False

    # Try using croniter for validation
    try:
        from croniter import croniter
        croniter(expression)
        return True
    except ImportError:
        pass
    except Exception:
        return False

    # Basic validation without croniter
    for part in parts:
        if part == "*":
            continue
        if part.startswith("*/"):
            try:
                int(part[2:])
                continue
            except ValueError:
                return False
        if "-" in part or "," in part:
            continue  # Range or list, assume valid
        try:
            int(part)
        except ValueError:
            return False

    return True


def cron_to_human(expression: str, timezone: str = "Asia/Shanghai") -> str:  # noqa: ARG001
    """Convert cron expression to human-readable description.

    Args:
        expression: Cron expression
        timezone: Timezone for display

    Returns:
        Human-readable description in Chinese
    """
    parts = expression.split()
    if len(parts) != 5:
        return f"Cron: {expression}"

    minute, hour, day, month, weekday = parts

    # Common patterns
    if day == "*" and month == "*":
        if weekday == "*":
            # Daily
            if minute == "0":
                return f"每天 {hour}:00"
            return f"每天 {hour}:{minute.zfill(2)}"
        else:
            # Weekly
            weekday_names = {
                "0": "周日", "1": "周一", "2": "周二", "3": "周三",
                "4": "周四", "5": "周五", "6": "周六", "7": "周日",
                "1-5": "工作日", "0,6": "周末", "6,0": "周末",
            }
            wd = weekday_names.get(weekday, f"周{weekday}")
            if minute == "0":
                return f"每{wd} {hour}:00"
            return f"每{wd} {hour}:{minute.zfill(2)}"

    # Interval patterns
    if minute.startswith("*/") and hour == "*" and day == "*" and month == "*" and weekday == "*":
        interval = minute[2:]
        return f"每隔 {interval} 分钟"

    if hour.startswith("*/") and minute == "0" and day == "*" and month == "*" and weekday == "*":
        interval = hour[2:]
        return f"每隔 {interval} 小时"

    return f"Cron: {expression}"


def interval_to_human(interval_ms: int) -> str:
    """Convert interval in milliseconds to human-readable description.

    Args:
        interval_ms: Interval in milliseconds

    Returns:
        Human-readable description in Chinese
    """
    seconds = interval_ms // 1000

    if seconds < 60:
        return f"每隔 {seconds} 秒"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"每隔 {minutes} 分钟"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"每隔 {hours} 小时"
    else:
        days = seconds // 86400
        return f"每隔 {days} 天"


def schedule_to_human(schedule: Schedule) -> str:
    """Convert schedule to human-readable description.

    Args:
        schedule: Schedule configuration

    Returns:
        Human-readable description in Chinese
    """
    if isinstance(schedule, AtSchedule):
        if schedule.at_ms > 0:
            dt = datetime.fromtimestamp(schedule.at_ms / 1000)
            return f"在 {dt.strftime('%Y-%m-%d %H:%M')} 执行一次"
        return "未设置执行时间"
    elif isinstance(schedule, EverySchedule):
        return interval_to_human(schedule.interval_ms)
    elif isinstance(schedule, CronSchedule):
        return cron_to_human(schedule.expression, schedule.timezone)
    return "未知调度类型"
