"""Core type definitions for the scheduler system.

Inspired by OpenClaw's architecture, this module defines:
- Schedule types (at/every/cron)
- Payload types (system_event/agent_turn/webhook/task_chain)
- Event types for the event system
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal


# ============== Schedule Types ==============

class ScheduleKind(str, Enum):
    """Kind of schedule."""
    AT = "at"           # One-time: execute at specific timestamp
    EVERY = "every"     # Interval: execute every N milliseconds
    CRON = "cron"       # Cron expression


@dataclass
class AtSchedule:
    """One-time schedule at a specific timestamp."""
    kind: Literal["at"] = "at"
    at_ms: int = 0  # Unix timestamp in milliseconds

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "at_ms": self.at_ms}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AtSchedule":
        return cls(at_ms=data.get("at_ms", 0))

    @classmethod
    def from_datetime(cls, dt: datetime) -> "AtSchedule":
        return cls(at_ms=int(dt.timestamp() * 1000))


@dataclass
class EverySchedule:
    """Interval-based schedule."""
    kind: Literal["every"] = "every"
    interval_ms: int = 0  # Interval in milliseconds

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "interval_ms": self.interval_ms}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EverySchedule":
        return cls(interval_ms=data.get("interval_ms", 0))

    @classmethod
    def from_seconds(cls, seconds: int) -> "EverySchedule":
        return cls(interval_ms=seconds * 1000)


@dataclass
class CronSchedule:
    """Cron expression schedule."""
    kind: Literal["cron"] = "cron"
    expression: str = ""  # Cron expression (5-part: min hour day month weekday)
    timezone: str = "Asia/Shanghai"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "expression": self.expression,
            "timezone": self.timezone,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CronSchedule":
        return cls(
            expression=data.get("expression", ""),
            timezone=data.get("timezone", "Asia/Shanghai"),
        )


# Union type for all schedule types
Schedule = AtSchedule | EverySchedule | CronSchedule


def schedule_from_dict(data: dict[str, Any]) -> Schedule:
    """Create a Schedule from a dictionary."""
    kind = data.get("kind", "at")
    if kind == "at":
        return AtSchedule.from_dict(data)
    elif kind == "every":
        return EverySchedule.from_dict(data)
    elif kind == "cron":
        return CronSchedule.from_dict(data)
    else:
        raise ValueError(f"Unknown schedule kind: {kind}")


# ============== Payload Types ==============

class PayloadKind(str, Enum):
    """Kind of job payload."""
    SYSTEM_EVENT = "system_event"  # Simple notification
    AGENT_TURN = "agent_turn"      # Agent execution
    WEBHOOK = "webhook"            # Webhook call
    TASK_CHAIN = "task_chain"      # Task chain trigger


@dataclass
class SystemEventPayload:
    """Simple system event/notification payload."""
    kind: Literal["system_event"] = "system_event"
    message: str = ""
    channel: str = "telegram"
    chat_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "message": self.message,
            "channel": self.channel,
            "chat_id": self.chat_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SystemEventPayload":
        return cls(
            message=data.get("message", ""),
            channel=data.get("channel", "telegram"),
            chat_id=data.get("chat_id", ""),
        )


@dataclass
class AgentTurnPayload:
    """Agent execution payload."""
    kind: Literal["agent_turn"] = "agent_turn"
    prompt: str = ""
    agent_id: str = "main"
    context: dict[str, Any] = field(default_factory=dict)
    notify_channel: str = "telegram"
    notify_chat_id: str = ""
    timeout_seconds: int = 300

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "prompt": self.prompt,
            "agent_id": self.agent_id,
            "context": self.context,
            "notify_channel": self.notify_channel,
            "notify_chat_id": self.notify_chat_id,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentTurnPayload":
        return cls(
            prompt=data.get("prompt", ""),
            agent_id=data.get("agent_id", "main"),
            context=data.get("context", {}),
            notify_channel=data.get("notify_channel", "telegram"),
            notify_chat_id=data.get("notify_chat_id", ""),
            timeout_seconds=data.get("timeout_seconds", 300),
        )


@dataclass
class WebhookPayload:
    """Webhook call payload."""
    kind: Literal["webhook"] = "webhook"
    url: str = ""
    method: str = "POST"
    headers: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 30

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "url": self.url,
            "method": self.method,
            "headers": self.headers,
            "body": self.body,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WebhookPayload":
        return cls(
            url=data.get("url", ""),
            method=data.get("method", "POST"),
            headers=data.get("headers", {}),
            body=data.get("body", {}),
            timeout_seconds=data.get("timeout_seconds", 30),
        )


@dataclass
class TaskChainPayload:
    """Task chain trigger payload."""
    kind: Literal["task_chain"] = "task_chain"
    next_job_id: str = ""
    on_status: list[str] = field(default_factory=lambda: ["ok"])  # Trigger conditions

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "next_job_id": self.next_job_id,
            "on_status": self.on_status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskChainPayload":
        return cls(
            next_job_id=data.get("next_job_id", ""),
            on_status=data.get("on_status", ["ok"]),
        )


# Union type for all payload types
Payload = SystemEventPayload | AgentTurnPayload | WebhookPayload | TaskChainPayload


def payload_from_dict(data: dict[str, Any]) -> Payload:
    """Create a Payload from a dictionary."""
    kind = data.get("kind", "agent_turn")
    if kind == "system_event":
        return SystemEventPayload.from_dict(data)
    elif kind == "agent_turn":
        return AgentTurnPayload.from_dict(data)
    elif kind == "webhook":
        return WebhookPayload.from_dict(data)
    elif kind == "task_chain":
        return TaskChainPayload.from_dict(data)
    else:
        raise ValueError(f"Unknown payload kind: {kind}")


# ============== Job Status ==============

class JobStatus(str, Enum):
    """Status of a scheduled job."""
    PENDING = "pending"       # Job created but not yet armed
    ACTIVE = "active"         # Job is armed and will execute
    PAUSED = "paused"         # Job is temporarily paused
    COMPLETED = "completed"   # One-time job completed
    FAILED = "failed"         # Job execution failed (max retries exceeded)


class RunStatus(str, Enum):
    """Status of a single job run."""
    OK = "ok"           # Run completed successfully
    FAILED = "failed"   # Run failed with error
    SKIPPED = "skipped" # Run was skipped
    TIMEOUT = "timeout" # Run timed out


# ============== Event Types ==============

class HookPoint(str, Enum):
    """Hook points in the scheduler lifecycle."""
    BEFORE_RUN = "before_run"
    AFTER_RUN = "after_run"
    ON_ERROR = "on_error"
    ON_COMPLETE = "on_complete"


@dataclass
class SchedulerEvent:
    """Event emitted by the scheduler."""
    type: str
    job_id: str
    timestamp_ms: int
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "job_id": self.job_id,
            "timestamp_ms": self.timestamp_ms,
            "payload": self.payload,
        }


# ============== Result Types ==============

@dataclass
class RunResult:
    """Result of a job run."""
    job_id: str
    status: RunStatus
    started_at_ms: int
    finished_at_ms: int
    result: Any = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "started_at_ms": self.started_at_ms,
            "finished_at_ms": self.finished_at_ms,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class RemoveResult:
    """Result of removing a job."""
    job_id: str
    removed: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "removed": self.removed,
            "reason": self.reason,
        }


@dataclass
class SchedulerStatus:
    """Status of the scheduler service."""
    running: bool
    jobs_total: int
    jobs_active: int
    jobs_paused: int
    next_run_at_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "jobs_total": self.jobs_total,
            "jobs_active": self.jobs_active,
            "jobs_paused": self.jobs_paused,
            "next_run_at_ms": self.next_run_at_ms,
        }
