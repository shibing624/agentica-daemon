from setuptools import setup, find_packages

setup(
    name="agentica-gateway",
    version="0.1.1",
    description="Agentica Gateway Service - Python OpenClaw",
    python_requires=">=3.10",
    packages=find_packages(),
    install_requires=[
        "agentica>=0.2.0",
        "fastapi>=0.109.0",
        "uvicorn>=0.27.0",
        "websockets>=12.0",
        "lark-oapi>=1.0.0",
        "apscheduler>=3.10.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
        "loguru>=0.7.0",
        "pyyaml>=6.0",
    ],
    extras_require={
        "telegram": ["python-telegram-bot>=20.0"],
        "discord": ["discord.py>=2.0"],
        "all": [
            "python-telegram-bot>=20.0",
            "discord.py>=2.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "agentica-gateway=src.main:main",
        ],
    },
)
