"""Tests for the scheduler module."""
import pytest
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.scheduler.models import ScheduledTask, TaskStatus, TaskType
from src.scheduler.task_parser import TaskParser, ParsedSchedule


class TestTaskParser:
    """Tests for natural language task parsing."""

    @pytest.fixture
    def parser(self):
        return TaskParser(llm_client=None)

    @pytest.mark.asyncio
    async def test_parse_daily_morning(self, parser):
        """Test parsing '每天早上9点'."""
        result = await parser.parse("每天早上9点提醒我看新闻")

        assert result.cron_expression == "0 9 * * *"
        assert result.confidence >= 0.8
        assert "看新闻" in result.parsed_action

    @pytest.mark.asyncio
    async def test_parse_every_hour(self, parser):
        """Test parsing '每小时'."""
        result = await parser.parse("每小时检查服务器状态")

        assert result.cron_expression == "0 * * * *"
        assert result.confidence >= 0.8

    @pytest.mark.asyncio
    async def test_parse_interval_minutes(self, parser):
        """Test parsing '每隔30分钟'."""
        result = await parser.parse("每隔30分钟检查邮件")

        assert result.interval_seconds == 1800
        assert result.confidence >= 0.8

    @pytest.mark.asyncio
    async def test_parse_tomorrow(self, parser):
        """Test parsing '明天上午10点'."""
        current = datetime(2024, 1, 15, 14, 0, 0)  # Monday 2pm
        result = await parser.parse("明天上午10点开会", current_time=current)

        assert result.run_at is not None
        assert result.run_at.day == 16
        assert result.run_at.hour == 10
        assert result.confidence >= 0.8

    @pytest.mark.asyncio
    async def test_parse_weekday(self, parser):
        """Test parsing '每周一'."""
        result = await parser.parse("每周一发送周报")

        assert result.cron_expression == "0 9 * * 1"
        assert result.confidence >= 0.8

    @pytest.mark.asyncio
    async def test_parse_english_daily(self, parser):
        """Test parsing English 'every day at 9am'."""
        result = await parser.parse("every day at 9 am check emails")

        assert result.cron_expression is not None
        assert "9" in result.cron_expression

    @pytest.mark.asyncio
    async def test_parse_workdays(self, parser):
        """Test parsing '工作日'."""
        result = await parser.parse("工作日每天9点站会")

        assert result.cron_expression == "0 9 * * 1-5"

    @pytest.mark.asyncio
    async def test_create_task_from_parse(self, parser):
        """Test creating task from parsed result."""
        parsed = ParsedSchedule(
            cron_expression="0 9 * * *",
            parsed_action="查看新闻",
            confidence=0.9,
        )

        task = parser.create_task_from_parse(
            parsed=parsed,
            original_prompt="每天早上9点提醒我查看新闻",
            user_id="user_123",
            notify_channel="telegram",
            notify_chat_id="12345",
        )

        assert task.user_id == "user_123"
        assert task.cron_expression == "0 9 * * *"
        assert task.parsed_action == "查看新闻"
        assert task.notify_channel == "telegram"


class TestScheduledTask:
    """Tests for ScheduledTask model."""

    def test_task_creation(self):
        """Test basic task creation."""
        task = ScheduledTask(
            user_id="user_123",
            prompt="每天早上9点看新闻",
            parsed_action="看新闻",
            cron_expression="0 9 * * *",
        )

        assert task.id is not None
        assert task.status == TaskStatus.PENDING
        assert task.task_type == TaskType.AGENT_RUN

    def test_task_serialization(self):
        """Test task to_dict/from_dict roundtrip."""
        task = ScheduledTask(
            user_id="user_123",
            prompt="test prompt",
            parsed_action="test action",
            cron_expression="0 9 * * *",
            notify_channel="telegram",
            notify_chat_id="12345",
        )

        data = task.to_dict()
        restored = ScheduledTask.from_dict(data)

        assert restored.id == task.id
        assert restored.user_id == task.user_id
        assert restored.cron_expression == task.cron_expression
        assert restored.status == task.status

    def test_task_with_run_at(self):
        """Test one-time task with run_at."""
        run_time = datetime.now() + timedelta(days=1)
        task = ScheduledTask(
            user_id="user_123",
            prompt="明天提醒",
            run_at=run_time,
        )

        data = task.to_dict()
        restored = ScheduledTask.from_dict(data)

        assert restored.run_at is not None
        assert restored.run_at.day == run_time.day


class TestCronToChineseConversion:
    """Tests for cron expression to Chinese conversion."""

    def test_daily_cron(self):
        from scheduler.tools import _cron_to_chinese

        assert "每天 9:00" == _cron_to_chinese("0 9 * * *")
        assert "每天 14:30" == _cron_to_chinese("30 14 * * *")

    def test_weekly_cron(self):
        from scheduler.tools import _cron_to_chinese

        result = _cron_to_chinese("0 9 * * 1")
        assert "周一" in result

        result = _cron_to_chinese("0 9 * * 1-5")
        assert "工作日" in result


# Integration test example
class TestSchedulerIntegration:
    """Integration tests for the full scheduler flow."""

    @pytest.mark.asyncio
    async def test_full_task_lifecycle(self, tmp_path):
        """Test creating, listing, and deleting a task."""
        from scheduler import SchedulerService, TaskParser, init_scheduler_tools
        from scheduler.tools import (
            create_scheduled_task_tool,
            list_scheduled_tasks_tool,
            delete_scheduled_task_tool,
        )

        # Setup
        db_path = tmp_path / "test_scheduler.db"
        scheduler = SchedulerService(db_path=db_path)
        parser = TaskParser()
        init_scheduler_tools(scheduler, parser)

        await scheduler.start()

        try:
            # Create task
            result = await create_scheduled_task_tool(
                task_description="每天早上9点测试",
                user_id="test_user",
            )
            assert result["success"] is True
            task_id = result["task"]["id"]

            # List tasks
            result = await list_scheduled_tasks_tool(user_id="test_user")
            assert result["success"] is True
            assert len(result["tasks"]) == 1

            # Delete task
            result = await delete_scheduled_task_tool(
                task_id=task_id,
                user_id="test_user",
            )
            assert result["success"] is True

            # Verify deleted
            result = await list_scheduled_tasks_tool(user_id="test_user")
            assert len(result["tasks"]) == 0

        finally:
            await scheduler.stop()
