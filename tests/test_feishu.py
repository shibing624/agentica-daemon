#!/usr/bin/env python3
"""测试飞书长连接 - 无需公网域名"""
import json
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
)

from autoworker.config import settings

if not settings.feishu_app_id or not settings.feishu_app_secret:
    raise ValueError("请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET 环境变量")


# 创建飞书客户端（用于发送消息）
client = (
    lark.Client.builder()
    .app_id(settings.feishu_app_id)
    .app_secret(settings.feishu_app_secret)
    .build()
)


def send_message(chat_id: str, text: str) -> bool:
    """发送文本消息"""
    request = (
        CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("text")
            .content(json.dumps({"text": text}))
            .build()
        )
        .build()
    )
    response = client.im.v1.message.create(request)
    if response.success():
        print(f"[发送成功] -> {text[:50]}...")
        return True
    else:
        print(f"[发送失败] code={response.code}, msg={response.msg}")
        return False


def on_message(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    """处理收到的消息"""
    try:
        message = data.event.message
        sender = data.event.sender

        # 基本信息
        msg_type = message.message_type
        chat_id = message.chat_id
        user_id = sender.sender_id.user_id if sender.sender_id else "unknown"

        print(f"\n[收到消息] type={msg_type}, chat_id={chat_id}, user={user_id}")

        # 白名单校验（空列表表示所有人可用）
        if settings.feishu_allowed_users and user_id not in settings.feishu_allowed_users:
            print(f"[拒绝] 用户 {user_id} 不在白名单中")
            send_message(chat_id, "⚠️ 未授权访问")
            return

        # 只处理文本消息
        if msg_type != "text":
            print(f"[跳过] 非文本消息: {msg_type}")
            return

        # 解析文本
        content = json.loads(message.content)
        text = content.get("text", "").strip()
        print(f"[文本内容] {text}")

        # 简单回复（Echo）
        reply = f"收到消息: {text}"
        send_message(chat_id, reply)

    except Exception as e:
        print(f"[错误] 处理消息失败: {e}")


def main():
    """启动飞书长连接"""
    print("=" * 50)
    print("飞书长连接测试")
    print(f"APP_ID: {settings.feishu_app_id[:10]}...")
    print(f"白名单: {'全部用户' if not settings.feishu_allowed_users else settings.feishu_allowed_users}")
    print("=" * 50)

    # 构建事件处理器
    # 注意：两个空字符串是 encrypt_key 和 verification_token，长连接模式不需要
    event_handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(on_message)
        .build()
    )

    # 创建 WebSocket 长连接客户端
    ws_client = lark.ws.Client(
        settings.feishu_app_id,
        settings.feishu_app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel.DEBUG,
    )

    print("\n[启动中] 正在建立长连接...")
    print("[提示] 请确保在飞书开放平台已启用「长连接」订阅方式")
    print("[提示] 向机器人发消息测试\n")

    # 启动（阻塞）
    ws_client.start()


if __name__ == "__main__":
    main()
