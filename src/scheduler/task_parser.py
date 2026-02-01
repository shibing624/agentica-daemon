"""Natural language parser for scheduled tasks using LLM."""
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .models import ScheduledTask, TaskType


@dataclass
class ParsedSchedule:
    """Result of parsing natural language schedule."""
    cron_expression: str | None = None
    interval_seconds: int | None = None
    run_at: datetime | None = None
    parsed_action: str = ""
    task_type: TaskType = TaskType.AGENT_RUN
    confidence: float = 0.0
    raw_parse: dict[str, Any] | None = None


# Common time pattern mappings for fallback parsing
TIME_PATTERNS = {
    # Chinese patterns
    r"每天早上(\d+)点": lambda m: f"0 {m.group(1)} * * *",
    r"每天上午(\d+)点": lambda m: f"0 {m.group(1)} * * *",
    r"每天下午(\d+)点": lambda m: f"0 {int(m.group(1)) + 12} * * *",
    r"每天晚上(\d+)点": lambda m: f"0 {int(m.group(1)) + 12} * * *",
    r"每天(\d+)点": lambda m: f"0 {m.group(1)} * * *",
    r"每周一": lambda m: "0 9 * * 1",
    r"每周二": lambda m: "0 9 * * 2",
    r"每周三": lambda m: "0 9 * * 3",
    r"每周四": lambda m: "0 9 * * 4",
    r"每周五": lambda m: "0 9 * * 5",
    r"每周六": lambda m: "0 9 * * 6",
    r"每周日": lambda m: "0 9 * * 0",
    r"每小时": lambda m: "0 * * * *",
    r"每(\d+)分钟": lambda m: f"*/{m.group(1)} * * * *",
    r"每(\d+)小时": lambda m: f"0 */{m.group(1)} * * *",
    r"工作日": lambda m: "0 9 * * 1-5",

    # English patterns
    r"every day at (\d+)(?::(\d+))?\s*(am|pm)?": lambda m: _parse_english_time(m),
    r"every (\d+) minutes?": lambda m: f"*/{m.group(1)} * * * *",
    r"every (\d+) hours?": lambda m: f"0 */{m.group(1)} * * *",
    r"every hour": lambda m: "0 * * * *",
    r"daily at (\d+)": lambda m: f"0 {m.group(1)} * * *",
    r"weekdays": lambda m: "0 9 * * 1-5",
    r"weekends": lambda m: "0 9 * * 0,6",
}

# Interval patterns (returns seconds)
INTERVAL_PATTERNS = {
    r"每隔(\d+)秒": lambda m: int(m.group(1)),
    r"每隔(\d+)分钟": lambda m: int(m.group(1)) * 60,
    r"每隔(\d+)小时": lambda m: int(m.group(1)) * 3600,
    r"every (\d+) seconds?": lambda m: int(m.group(1)),
}


def _parse_english_time(m: re.Match) -> str:
    """Parse English time format like '9:30 am'."""
    hour = int(m.group(1))
    minute = int(m.group(2)) if m.group(2) else 0
    period = m.group(3)
    if period and period.lower() == "pm" and hour < 12:
        hour += 12
    elif period and period.lower() == "am" and hour == 12:
        hour = 0
    return f"{minute} {hour} * * *"


class TaskParser:
    """Parses natural language into structured scheduled tasks.

    Uses LLM for complex parsing with rule-based fallback for common patterns.
    """

    # System prompt for LLM parsing
    PARSE_SYSTEM_PROMPT = """你是一个专门解析自然语言定时任务的助手。

用户会给你一段自然语言描述的定时任务，你需要提取以下信息：

1. **schedule_type**: 调度类型
   - "cron": 周期性任务（每天、每周、每月等）
   - "interval": 间隔执行（每隔N分钟/小时）
   - "once": 一次性任务（明天下午3点、下周一等）

2. **cron_expression**: 如果是cron类型，给出cron表达式（5位：分 时 日 月 周）

3. **interval_seconds**: 如果是interval类型，给出间隔秒数

4. **run_at**: 如果是once类型，给出ISO格式的执行时间

5. **action**: 要执行的动作描述（去掉时间相关的词，只保留动作）

6. **task_type**: 任务类型
   - "agent_run": 需要AI执行的任务（默认）
   - "notification": 简单提醒/通知
   - "webhook": 调用外部API

请以JSON格式返回，示例：
```json
{
  "schedule_type": "cron",
  "cron_expression": "0 9 * * *",
  "action": "查看今日新闻并总结",
  "task_type": "agent_run",
  "confidence": 0.95
}
```

注意：
- cron表达式使用5位格式：分 时 日 月 周
- 周：0-6（0=周日）或 1-7（1=周一）
- 时间默认使用24小时制
- 如果时间表述模糊，给出最合理的解释并降低confidence"""

    def __init__(self, llm_client: Any | None = None):
        """Initialize parser with optional LLM client.

        Args:
            llm_client: LLM client for complex parsing. If None, uses rule-based only.
        """
        self.llm_client = llm_client

    async def parse(
        self,
        text: str,
        user_timezone: str = "Asia/Shanghai",
        current_time: datetime | None = None,
    ) -> ParsedSchedule:
        """Parse natural language into a structured schedule.

        Args:
            text: Natural language task description
            user_timezone: User's timezone for time calculations
            current_time: Current time (for testing), defaults to now

        Returns:
            ParsedSchedule with extracted schedule information
        """
        current_time = current_time or datetime.now()

        # Try rule-based parsing first for common patterns
        result = self._rule_based_parse(text, current_time)
        if result.confidence >= 0.8:
            return result

        # Use LLM for complex parsing if available
        if self.llm_client:
            llm_result = await self._llm_parse(text, user_timezone, current_time)
            # Use LLM result if it has higher confidence
            if llm_result.confidence > result.confidence:
                return llm_result

        return result

    def _rule_based_parse(
        self, text: str, current_time: datetime
    ) -> ParsedSchedule:
        """Fallback rule-based parsing for common patterns."""
        text_lower = text.lower()
        result = ParsedSchedule()

        # Try interval patterns first
        for pattern, handler in INTERVAL_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result.interval_seconds = handler(match)
                result.parsed_action = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
                result.confidence = 0.85
                return result

        # Try cron patterns
        for pattern, handler in TIME_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result.cron_expression = handler(match)
                result.parsed_action = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
                result.confidence = 0.85
                return result

        # Check for relative time expressions (one-time tasks)
        relative_result = self._parse_relative_time(text, current_time)
        if relative_result:
            return relative_result

        # If no schedule pattern found, treat as immediate task
        result.parsed_action = text
        result.run_at = current_time + timedelta(minutes=1)  # Run in 1 minute
        result.confidence = 0.3  # Low confidence - no clear schedule
        return result

    def _parse_relative_time(
        self, text: str, current_time: datetime
    ) -> ParsedSchedule | None:
        """Parse relative time expressions like '明天', '下周一'."""
        result = ParsedSchedule()

        # Tomorrow patterns
        if "明天" in text or "tomorrow" in text.lower():
            # Extract hour if specified
            hour_match = re.search(r"(\d+)点|(\d+):(\d+)", text)
            hour = 9  # Default to 9 AM
            minute = 0
            if hour_match:
                if hour_match.group(1):
                    hour = int(hour_match.group(1))
                elif hour_match.group(2):
                    hour = int(hour_match.group(2))
                    minute = int(hour_match.group(3)) if hour_match.group(3) else 0

            # Adjust for afternoon/evening
            if any(x in text for x in ["下午", "晚上", "pm", "PM"]) and hour < 12:
                hour += 12

            tomorrow = current_time + timedelta(days=1)
            result.run_at = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
            result.parsed_action = re.sub(
                r"明天|tomorrow|\d+点|\d+:\d+|上午|下午|晚上|am|pm",
                "", text, flags=re.IGNORECASE
            ).strip()
            result.confidence = 0.85
            return result

        # Next week patterns
        weekday_map = {
            "周一": 0, "周二": 1, "周三": 2, "周四": 3,
            "周五": 4, "周六": 5, "周日": 6,
            "monday": 0, "tuesday": 1, "wednesday": 2,
            "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
        }

        for day_name, weekday in weekday_map.items():
            if day_name in text.lower() and ("下" in text or "next" in text.lower()):
                days_ahead = weekday - current_time.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                target_date = current_time + timedelta(days=days_ahead)
                result.run_at = target_date.replace(hour=9, minute=0, second=0, microsecond=0)
                result.parsed_action = text
                result.confidence = 0.8
                return result

        return None

    async def _llm_parse(
        self,
        text: str,
        user_timezone: str,
        current_time: datetime,
    ) -> ParsedSchedule:
        """Use LLM for complex natural language parsing."""
        result = ParsedSchedule()

        if not self.llm_client:
            return result

        try:
            # Call LLM with parsing prompt
            user_prompt = f"""当前时间: {current_time.isoformat()}
用户时区: {user_timezone}

请解析以下定时任务描述:
"{text}"
"""
            # This assumes an OpenAI-compatible client
            response = await self.llm_client.chat.completions.create(
                model="gpt-4o-mini",  # Use a fast model for parsing
                messages=[
                    {"role": "system", "content": self.PARSE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            # Parse JSON response
            content = response.choices[0].message.content
            if content:
                parsed = json.loads(content)
                result.raw_parse = parsed
                result.confidence = parsed.get("confidence", 0.7)
                result.parsed_action = parsed.get("action", text)
                result.task_type = TaskType(parsed.get("task_type", "agent_run"))

                schedule_type = parsed.get("schedule_type", "")
                if schedule_type == "cron" and parsed.get("cron_expression"):
                    result.cron_expression = parsed["cron_expression"]
                elif schedule_type == "interval" and parsed.get("interval_seconds"):
                    result.interval_seconds = parsed["interval_seconds"]
                elif schedule_type == "once" and parsed.get("run_at"):
                    result.run_at = datetime.fromisoformat(parsed["run_at"])

        except Exception as e:
            # Log error but don't fail - fallback to rule-based
            print(f"LLM parsing failed: {e}")
            result.confidence = 0.0

        return result

    def create_task_from_parse(
        self,
        parsed: ParsedSchedule,
        original_prompt: str,
        user_id: str,
        notify_channel: str = "telegram",
        notify_chat_id: str = "",
    ) -> ScheduledTask:
        """Create a ScheduledTask from parsed schedule result."""
        return ScheduledTask(
            user_id=user_id,
            task_type=parsed.task_type,
            prompt=original_prompt,
            parsed_action=parsed.parsed_action,
            cron_expression=parsed.cron_expression,
            interval_seconds=parsed.interval_seconds,
            run_at=parsed.run_at,
            notify_channel=notify_channel,
            notify_chat_id=notify_chat_id,
        )
