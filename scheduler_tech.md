# Agentica Daemon - Scheduled Tasks

自然语言定时任务调度系统，支持用户通过对话创建、管理定时任务。

## 架构概览

```
用户输入                    Agent 层                    调度层                    执行层
────────────────────────────────────────────────────────────────────────────────────────
"每天早上9点          ┌──────────────┐         ┌─────────────────┐        ┌─────────────┐
 提醒我看新闻"   ───▶ │  TaskParser  │────────▶│SchedulerService│───────▶│TaskExecutor │
                      │  (NL解析)    │         │  (APScheduler)  │        │ (Agent调用) │
                      └──────────────┘         └─────────────────┘        └─────────────┘
                             │                         │                        │
                             ▼                         ▼                        ▼
                      ┌──────────────┐         ┌─────────────────┐        ┌─────────────┐
                      │ ParsedSchedule│        │   SQLite DB     │        │ 通知发送    │
                      │ cron: 0 9 * *│         │   (持久化)      │        │ Telegram等  │
                      └──────────────┘         └─────────────────┘        └─────────────┘
```

## 核心模块

### 1. TaskParser - 自然语言解析

将用户的自然语言转换为结构化调度配置：

```python
from scheduler import TaskParser

parser = TaskParser(llm_client=openai_client)  # 可选 LLM

result = await parser.parse("每天早上9点提醒我看新闻")
# ParsedSchedule(
#     cron_expression="0 9 * * *",
#     parsed_action="提醒我看新闻",
#     confidence=0.9
# )
```

支持的时间表达式：
- 周期性：`每天早上9点`、`每周一下午3点`、`工作日9点`
- 间隔型：`每隔30分钟`、`每小时`
- 一次性：`明天上午10点`、`下周一`

### 2. SchedulerService - APScheduler 集成

管理任务的生命周期和 APScheduler 交互：

```python
from scheduler import SchedulerService

scheduler = SchedulerService(
    db_path="~/.agentica/scheduler.db",
    executor=task_executor.execute,  # 执行回调
)

await scheduler.start()

# 添加任务
task = await scheduler.add_task(scheduled_task)

# 任务会在指定时间自动执行
```

特性：
- SQLite 持久化（任务+APScheduler jobs）
- 自动恢复（daemon 重启后）
- 错误重试
- 任务状态管理

### 3. Tools - Agent 工具

为 Agent 框架提供的工具定义：

```python
from scheduler import init_scheduler_tools, ALL_SCHEDULER_TOOLS

# 初始化
init_scheduler_tools(scheduler_service, task_parser)

# 注册到 Agent
tools = [{"type": "function", "function": t} for t in ALL_SCHEDULER_TOOLS]
```

提供的工具：
- `create_scheduled_task` - 创建定时任务
- `list_scheduled_tasks` - 列出任务
- `delete_scheduled_task` - 删除任务

## 使用示例

### 1. 基本设置

```python
import asyncio
from scheduler import SchedulerService, TaskParser, init_scheduler_tools
from scheduler.executor import TaskExecutor, SimpleAgentRunner

async def main():
    # 创建组件
    parser = TaskParser()
    executor = TaskExecutor(agent_runner=SimpleAgentRunner())
    scheduler = SchedulerService(executor=executor.execute)

    # 初始化工具
    init_scheduler_tools(scheduler, parser)

    # 启动
    await scheduler.start()

    # ... 运行你的 agent 或 API 服务

asyncio.run(main())
```

### 2. Agent 对话流程

```
用户: 帮我设置一个定时任务，每天早上9点提醒我查看新闻

Agent: [调用 create_scheduled_task 工具]
       {
         "task_description": "每天早上9点提醒我查看新闻",
         "user_id": "user_123",
         "notify_channel": "telegram",
         "notify_chat_id": "12345678"
       }

系统: [TaskParser 解析] → [SchedulerService 注册 APScheduler job]

Agent: 已创建定时任务！
       - 任务：提醒我查看新闻
       - 时间：每天 9:00
       - 下次执行：明天 09:00
```

### 3. 自定义执行器

```python
class MyAgentRunner:
    """自定义 Agent 执行器"""

    async def run(self, prompt: str, context: dict) -> str:
        # 调用你的 Agent 系统
        result = await my_agent.chat(prompt)
        return result

executor = TaskExecutor(
    agent_runner=MyAgentRunner(),
    notification_sender=MyNotificationSender(),
)
```

## 数据流详解

### 创建任务

```
1. 用户输入 "每天早上9点提醒我看新闻"
   ↓
2. TaskParser.parse()
   - 规则匹配: 匹配 "每天早上(\d+)点" → cron: "0 9 * * *"
   - 或 LLM 解析（复杂表达式）
   ↓
3. ParsedSchedule
   {
     cron_expression: "0 9 * * *",
     parsed_action: "提醒我看新闻",
     confidence: 0.9
   }
   ↓
4. SchedulerService.add_task()
   - 保存到 SQLite
   - 创建 APScheduler CronTrigger job
   ↓
5. 返回确认信息给用户
```

### 任务执行

```
1. APScheduler 触发 (每天 9:00)
   ↓
2. SchedulerService._execute_task(task_id)
   - 从数据库加载任务
   ↓
3. TaskExecutor.execute(task)
   - AGENT_RUN: 调用 AgentRunner.run()
   - NOTIFICATION: 调用 NotificationSender.send()
   ↓
4. 更新任务状态
   - last_run_at, run_count, next_run_at
   ↓
5. 发送结果通知（如果配置）
```

## 安装

```bash
cd agentica-daemon
pip install -e ".[dev]"

# 可选：OpenAI 支持（用于 LLM 解析）
pip install -e ".[openai]"

# 可选：Telegram 通知
pip install -e ".[telegram]"
```

## 运行测试

```bash
pytest scheduler/tests/
```

## 配置

环境变量：
- `AGENTICA_DB_PATH` - 数据库路径（默认 `~/.agentica/scheduler.db`）
- `AGENTICA_TIMEZONE` - 默认时区（默认 `Asia/Shanghai`）

## 扩展

### 添加新的通知渠道

```python
class WeChatNotificationSender:
    async def send(self, channel: str, chat_id: str, message: str) -> bool:
        if channel == "wechat":
            # 调用微信 API
            return True
        return False
```

### 添加新的任务类型

1. 在 `models.py` 的 `TaskType` 枚举添加新类型
2. 在 `executor.py` 的 `TaskExecutor.execute()` 添加处理逻辑
