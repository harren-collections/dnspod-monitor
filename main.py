# -*- coding: utf-8 -*-
import requests
import json
import time
import os
import sys
from datetime import datetime


previous_records_state = {}
dnspod_ua = "DNSPod Record Monitor/1.0"

def load_config():
    """
    加载并验证 config.json 配置文件。
    """
    config_path = 'config.json'
    if not os.path.exists(config_path):
        print(f"错误: 配置文件 {config_path} 不存在，请参考仓库中的配置文件模版创建配置。")
        sys.exit(1)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 验证关键配置是否存在
        required_keys = ['domain', 'token', 'names', 'telegram_bot_token', 'telegram_chat_id']
        for key in required_keys:
            if key not in config:
                print(f"错误: 配置文件中缺少必要的键: '{key}'，请参考仓库中的配置文件模版修改配置。")
                sys.exit(1)
        
        # 如果未设置检查间隔，则提供一个默认值
        if 'check_interval_seconds' not in config:
            config['check_interval_seconds'] = 10
            
        return config
    except json.JSONDecodeError:
        print(f"错误: 配置文件 {config_path} 格式不正确，无法解析 JSON。")
        sys.exit(1)
    except Exception as e:
        print(f"加载配置文件时发生未知错误: {e}")
        sys.exit(1)

def send_telegram_message(bot_token, chat_id, message):
    """
    通过 Telegram Bot API 发送消息。
    """
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'Markdown' # 使用 Markdown 格式化消息
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200 and response.json().get("ok"):
            print("Telegram 通知发送成功。")
        else:
            print(f"Telegram 通知发送失败: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"连接 Telegram API 时发生网络错误: {e}")

def get_dnspod_records(domain, token):
    """
    从 DNSPod API 获取域名记录列表。
    """
    url = "https://dnsapi.cn/Record.List"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": dnspod_ua
    }
    data = {
        "login_token": token,
        "domain": domain,
        "format": "json"
    }
    
    try:
        response = requests.post(url, headers=headers, data=data, timeout=5)
        response.raise_for_status()  # 如果 HTTP 状态码不是 2xx，则抛出异常
        
        result = response.json()
        
        # 检查 DNSPod API 返回的状态码
        if result.get("status", {}).get("code") == "1":
            return result.get("records", [])
        else:
            error_message = result.get("status", {}).get("message", "未知API错误")
            print(f"DNSPod API 返回错误: {error_message}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"请求 DNSPod API 时发生网络错误: {e}")
        return None
    except json.JSONDecodeError:
        print("解析 DNSPod API 响应失败，不是有效的 JSON。")
        return None

def format_records_for_display(records_list):
    """
    将记录列表格式化为易于阅读的字符串。
    """
    if not records_list:
        return "无"
    # 按类型和值排序，以确保一致性
    sorted_records = sorted(records_list, key=lambda x: (x['type'], x['value']))
    return "\n".join([f"  - 类型: {r['type']}, 值: {r['value']}" for r in sorted_records])

def check_for_changes(config):
    """
    核心检查逻辑：获取、比较并发送通知。
    """
    global previous_records_state
    
    domain = config['domain']
    token = config['token']
    names_to_monitor = set(config['names']) # 使用集合以提高查找效率
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始检查域名 '{domain}' 的记录...")
    
    all_records = get_dnspod_records(domain, token)
    
    if all_records is None:
        print("获取记录失败，跳过本次检查。")
        return

    # 提取并构建当前需要监控的记录状态
    current_records_state = {}
    for record in all_records:
        if record['name'] in names_to_monitor:
            subdomain = record['name']
            record_info = {
                "type": record['type'],
                "value": record['value']
            }
            if subdomain not in current_records_state:
                current_records_state[subdomain] = []
            current_records_state[subdomain].append(record_info)

    # 如果是第一次运行，则初始化状态并退出
    if not previous_records_state:
        print("首次运行，正在初始化记录状态...")
        previous_records_state = current_records_state
        print("初始化完成。")
        return

    # 比较当前状态和上一次的状态
    if current_records_state != previous_records_state:
        print("检测到 DNS 记录发生变化！")
        
        # 找出具体是哪个子域名发生了变化
        all_monitored_names = set(previous_records_state.keys()) | set(current_records_state.keys())
        
        for name in all_monitored_names:
            # 为了确保比较的准确性，对记录列表进行排序
            old_list = sorted(previous_records_state.get(name, []), key=lambda x: (x['type'], x['value']))
            new_list = sorted(current_records_state.get(name, []), key=lambda x: (x['type'], x['value']))

            if old_list != new_list:
                full_domain = f"{name}.{domain}"
                print(f"子域名 {full_domain} 的记录已变更。")
                
                # 构建通知消息
                message = (
                    f"⚠️ *DNSPod 记录变更通知*\n\n"
                    f"*域名*: `{full_domain}`\n\n"
                    f"*旧记录*:\n{format_records_for_display(old_list)}\n\n"
                    f"*新记录*:\n{format_records_for_display(new_list)}"
                )
                
                # 发送通知
                send_telegram_message(
                    config['telegram_bot_token'],
                    config['telegram_chat_id'],
                    message
                )
        
        # 更新状态
        previous_records_state = current_records_state
    else:
        print("记录无变化。")


if __name__ == "__main__":
    print("--- DNSPod 记录监控脚本 ---")
    
    # 1. 加载配置
    config = load_config()
    print("配置加载成功。")
    print(f"监控域名: {config['domain']}")
    print(f"监控子域名: {', '.join(config['names'])}")
    print(f"检查间隔: {config['check_interval_seconds']} 秒")
    
    # 2. 启动主循环
    try:
        while True:
            check_for_changes(config)
            time.sleep(config['check_interval_seconds'])
    except KeyboardInterrupt:
        print("\n检测到 Ctrl+C，正在退出脚本...")
        sys.exit(0)
    except Exception as e:
        print(f"\n脚本主循环发生未捕获的异常: {e}")
        sys.exit(1)
