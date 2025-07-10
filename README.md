# 监听 DNSPod 域名 IP 变化

本工具可以监听 DNSPod 上的域名 IP 变化并向 Telegram 发送通知，常用于动态域名场景。可基于现有代码进一步开发，实现更多功能。

## 配置说明

domain: 主域名

token: DNSPod Token

names: 需要监听的子域名

telegram_bot_token: Telegram 机器人 Token

telegram_chat_id: Telegram 推送会话 ID

check_interval_seconds: 监听间隔
