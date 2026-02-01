"""Agent 服务 - 封装 agentica SDK"""
from dataclasses import dataclass
from typing import Optional, Callable, List, Any
from pathlib import Path

from loguru import logger
from agentica import Agent, DeepAgent, OpenAIChat, ZhipuAI

from ..config import settings


@dataclass
class ChatResult:
    """聊天结果"""
    content: str
    tool_calls: int = 0
    session_id: str = ""


class AgentService:
    """Agent 服务

    封装 agentica SDK，提供统一的 Agent 调用接口
    """

    def __init__(
        self,
        workspace_path: Optional[str] = None,
        model_name: Optional[str] = None,
        model_provider: Optional[str] = None,
    ):
        self.workspace_path = Path(workspace_path or settings.workspace_path).expanduser()
        self.model_name = model_name or settings.model_name
        self.model_provider = model_provider or settings.model_provider

        # 延迟初始化
        self._agent = None
        self._initialized = False

    def _ensure_initialized(self):
        """确保已初始化"""
        if self._initialized:
            return

        try:
            # 创建模型
            model = self._create_model()

            # 创建 Agent
            self._agent = DeepAgent(
                model=model,
                add_datetime_to_instructions=True,
            )

            self._initialized = True
            logger.info("AgentService initialized")
            logger.info(f"Model: {self.model_provider}/{self.model_name}")

        except Exception as e:
            logger.error(f"AgentService init error: {e}")
            logger.warning("Running in mock mode")
            self._initialized = True

    def _create_model(self) -> Any:
        """创建模型实例"""
        if self.model_provider == "zhipuai":
            from agentica import ZhipuAI
            return ZhipuAI(model=self.model_name)
        elif self.model_provider == "openai":
            from agentica import OpenAIChat
            return OpenAIChat(model=self.model_name)
        elif self.model_provider == "deepseek":
            from agentica import DeepSeek
            return DeepSeek(model=self.model_name)
        else:
            # 默认使用 OpenAI 兼容接口
            from agentica import OpenAILike
            return OpenAILike(model=self.model_name)

    async def chat(
        self,
        message: str,
        session_id: str = "default",
    ) -> ChatResult:
        """处理聊天消息

        Args:
            message: 用户消息
            session_id: 会话ID

        Returns:
            聊天结果
        """
        self._ensure_initialized()

        if not self._agent:
            # Mock 模式
            return ChatResult(
                content=f"[Mock] Received: {message}",
                tool_calls=0,
                session_id=session_id,
            )

        try:
            # 运行 Agent
            response = await self._agent.arun(
                message,
                session_id=session_id,
            )

            content = (response.content or "").strip()
            return ChatResult(
                content=content,
                tool_calls=len(response.tools) if response.tools else 0,
                session_id=session_id,
            )

        except Exception as e:
            logger.error(f"AgentService chat error: {e}")
            return ChatResult(
                content=f"Error: {e}",
                tool_calls=0,
                session_id=session_id,
            )

    async def chat_stream(
        self,
        message: str,
        session_id: str = "default",
        on_content: Optional[Callable[[str], Any]] = None,
    ) -> ChatResult:
        """流式聊天

        Args:
            message: 用户消息
            session_id: 会话ID
            on_content: 内容回调

        Returns:
            聊天结果
        """
        self._ensure_initialized()

        if not self._agent:
            # Mock 模式
            content = f"[Mock] Received: {message}"
            if on_content:
                await on_content(content)
            return ChatResult(
                content=content,
                tool_calls=0,
                session_id=session_id,
            )

        try:
            # 流式运行
            full_content = ""
            tool_calls = 0

            async for chunk in self._agent.arun_stream(
                message,
                session_id=session_id,
            ):
                if chunk.content:
                    full_content += chunk.content
                    if on_content:
                        await on_content(chunk.content)

                if chunk.tools:
                    tool_calls += len(chunk.tools)

            return ChatResult(
                content=full_content.strip(),
                tool_calls=tool_calls,
                session_id=session_id,
            )

        except Exception as e:
            logger.error(f"AgentService stream error: {e}")
            return ChatResult(
                content=f"Error: {e}",
                tool_calls=0,
                session_id=session_id,
            )

    def save_memory(self, content: str, long_term: bool = False):  # noqa: ARG002
        """保存记忆"""
        self._ensure_initialized()

        if self._agent and hasattr(self._agent, 'save_memory'):
            self._agent.save_memory(content, long_term=long_term)

    def list_sessions(self) -> List[str]:
        """列出所有会话"""
        sessions_dir = self.workspace_path.parent / "sessions"
        if sessions_dir.exists():
            return [f.stem for f in sessions_dir.glob("*.json")]
        return []

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        sessions_dir = self.workspace_path.parent / "sessions"
        session_file = sessions_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
            return True
        return False
