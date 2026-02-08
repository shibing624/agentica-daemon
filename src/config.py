"""配置管理 - FastAPI 服务配置"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

from dotenv import load_dotenv
load_dotenv(override=True)


@dataclass
class Settings:
    """服务配置"""

    # 服务配置
    host: str = "0.0.0.0"
    port: int = 8789
    debug: bool = False
    gateway_token: Optional[str] = None

    # 默认用户ID（单用户场景）
    default_user_id: str = "default"

    # 工作空间（agent 数据/配置存储）
    workspace_path: Path = field(default_factory=lambda: Path.home() / ".agentica" / "workspace")
    data_dir: Path = field(default_factory=lambda: Path.home() / ".agentica" / "data")
    # Agent 工作目录（shell 命令执行的 cwd，默认用户 home）
    base_dir: Path = field(default_factory=Path.home)

    # 模型配置
    model_provider: str = "zhipuai"
    model_name: str = "glm-4.7-flash"
    model_thinking: str = ""  # 思考模式：enabled / disabled / auto，空则不启用

    # 飞书
    feishu_app_id: Optional[str] = None
    feishu_app_secret: Optional[str] = None
    feishu_allowed_users: List[str] = field(default_factory=list)
    feishu_allowed_groups: List[str] = field(default_factory=list)

    # Telegram
    telegram_bot_token: Optional[str] = None
    telegram_allowed_users: List[str] = field(default_factory=list)

    # Discord
    discord_bot_token: Optional[str] = None
    discord_allowed_users: List[str] = field(default_factory=list)
    discord_allowed_guilds: List[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "Settings":
        """从环境变量加载配置"""
        allowed_users = os.getenv("FEISHU_ALLOWED_USERS", "")
        allowed_groups = os.getenv("FEISHU_ALLOWED_GROUPS", "")

        return cls(
            # 服务
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8789")),
            debug=os.getenv("DEBUG", "").lower() in ("1", "true"),
            gateway_token=os.getenv("GATEWAY_TOKEN"),

            # 默认用户ID
            default_user_id=os.getenv("DEFAULT_USER_ID", "default"),

            # 路径
            workspace_path=Path(os.getenv(
                "AGENTICA_WORKSPACE_DIR", str(Path.home() / ".agentica" / "workspace")
            )),
            data_dir=Path(os.getenv(
                "AGENTICA_DATA_DIR", str(Path.home() / ".agentica" / "data")
            )),
            base_dir=Path(os.getenv(
                "AGENTICA_BASE_DIR", str(Path.home())
            )),

            # 模型
            model_provider=os.getenv("AGENTICA_MODEL_PROVIDER", "zhipuai"),
            model_name=os.getenv("AGENTICA_MODEL_NAME", "glm-4.7-flash"),
            model_thinking=os.getenv("AGENTICA_MODEL_THINKING", ""),

            # 飞书
            feishu_app_id=os.getenv("FEISHU_APP_ID"),
            feishu_app_secret=os.getenv("FEISHU_APP_SECRET"),
            feishu_allowed_users=[
                u.strip() for u in allowed_users.split(",") if u.strip()
            ],
            feishu_allowed_groups=[
                g.strip() for g in allowed_groups.split(",") if g.strip()
            ],

            # Telegram
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            telegram_allowed_users=[
                u.strip() for u in os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",") if u.strip()
            ],

            # Discord
            discord_bot_token=os.getenv("DISCORD_BOT_TOKEN"),
            discord_allowed_users=[
                u.strip() for u in os.getenv("DISCORD_ALLOWED_USERS", "").split(",") if u.strip()
            ],
            discord_allowed_guilds=[
                g.strip() for g in os.getenv("DISCORD_ALLOWED_GUILDS", "").split(",") if g.strip()
            ],
        )


# 全局配置实例
settings = Settings.from_env()
