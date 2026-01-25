import requests
import json
import time
import re
import os
import random
import sys
from fake_useragent import UserAgent

# ================= 配置区 =================
DEBUG_MODE = False  # 设置为 True 则进入测试模式，不发送实际请求
MAX_CONTINUOUS_ERRORS = 5
VID_FILE = "vid.json"
TARGET_PATTERN = "2PAAf74aG3D61qvfKUM5dxUssJQ9"
# =========================================

def log(msg, level="INFO"):
    """实时打印日志函数"""
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    icons = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️", "DEBUG": "🔍"}
    # flush=True 保证 GitHub Action 实时显示
    print(f"[{timestamp}] {icons.get(level, '•')} {msg}", flush=True)

def run_task():
    log("🚀 京东多账号轮询任务启动", "INFO")
    
    if not os.path.exists(VID_FILE):
        log(f"找不到配置文件: {VID_FILE}", "ERROR")
        return

    try:
        with open(VID_FILE, "r") as f:
            vender_ids = json.load(f)
    except Exception as e:
        log(f"VID 文件解析失败: {e}", "ERROR")
        return

    # 初始化 UA
    try:
        ua = UserAgent()
    except:
        ua = None

    error_count = 0
    url = "https://api.m.jd.com/client.action"

    for vid in vender_ids:
        if error_count >= MAX_CONTINUOUS_ERRORS:
            log(f"已连续报错 {MAX_CONTINUOUS_ERRORS} 次，触发熔断，程序退出。", "ERROR")
            sys.exit(1)

        random_ua = ua.random if ua else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        log(f"正在处理 VenderID: {vid} (当前连续错误: {error_count})", "INFO")

        if DEBUG_MODE:
            log(f"[测试模式] 模拟请求 VID: {vid}, 使用 UA: {random_ua[:40]}...", "DEBUG")
            time.sleep(0.5)
            continue

        # 构造请求
        current_t = str(int(time.time() * 1000))
        headers = {
            "accept": "*/*",
            "content-type": "application/x-www-form-urlencoded",
            "referer": "https://shop.m.jd.com/",
            "user-agent": random_ua,
            "x-rp-client": "h5_1.0.0"
        }
        data = {
            "functionId": "whx_getShopHomeActivityInfo",
            "body": json.dumps({"venderId": str(vid), "source": "m-shop"}),
            "t": current_t,
            "appid": "shop_m_jd_com",
            "clientVersion": "11.0.0",
            "client": "wh5",
            "x-api-eid-token": "jdd03K6QR2YT3GL7KPXOLIFG637VJG2VAQ63BLVYVW4IF3LG7CTBI7T2EUN42IUOJQMG4TOVKQXXZMB43ZQ7CNUOAOWFARYAAAAM36NROQYYAAAAACED3TOGFVFNEJMX"
        }

        try:
            response = requests.post(url, headers=headers, data=data, timeout=10)
            
            if response.status_code != 200:
                error_count += 1
                log(f"HTTP 状态异常: {response.status_code}", "WARN")
                continue

            res_json = response.json()
            if res_json.get("code") != "0":
                error_count += 1
                log(f"业务请求失败: {res_json.get('msg', '未知错误')}", "WARN")
                continue

            # 成功则重置计数
            error_count = 0
            
            isv_url = res_json.get("result", {}).get("signStatus", {}).get("isvUrl", "")
            if TARGET_PATTERN in isv_url:
                token_match = re.search(r'token=([^&]+)', isv_url)
                token = token_match.group(1) if token_match else "Missing"
                log(f"匹配成功! Token: {token}", "SUCCESS")
                log(f"完整链接: {isv_url}", "DEBUG")
            else:
                log(f"VID {vid} 无目标活动", "INFO")

            time.sleep(random.uniform(2, 4))

        except Exception as e:
            error_count += 1
            log(f"网络异常: {e}", "ERROR")

    log("🏁 所有任务处理完毕", "SUCCESS")

if __name__ == "__main__":
    run_task()
