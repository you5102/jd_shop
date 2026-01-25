import os
import json
import time
import re
import random
import base64
import sys
from playwright.sync_api import sync_playwright
from proxy import XieQuManager # 引用刚才写的代理类

# ================= 配置区 =================
TARGET_PATTERN = "2PAAf74aG3D61qvfKUM5dxUssJQ9"
# =========================================

def log(msg, level="INFO"):
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    icons = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️", "PROXY": "🌐"}
    print(f"[{timestamp}] {icons.get(level, '•')} {msg}", flush=True)

def get_decoded_account():
    """从环境变量读取并解码账号信息"""
    try:
        raw_data = os.environ.get("PROXY_INFO", "")
        if not raw_data:
            return None
        # 解码 Base64
        decoded_bytes = base64.b64decode(raw_data)
        accounts = json.loads(decoded_bytes.decode('utf-8'))
        # 随机选择一组账号使用
        return random.choice(accounts) if isinstance(accounts, list) else accounts
    except Exception as e:
        log(f"账号解码失败: {e}", "ERROR")
        return None

def run_task():
    # 1. 初始化代理管理器
    uid = os.environ.get("XQ_UID")
    ukey = os.environ.get("XQ_UKEY")
    if not uid or not ukey:
        log("缺少 XQ_UID 或 XQ_UKEY 环境变量", "ERROR")
        return

    xq = XieQuManager(uid, ukey)
    my_ip = xq.get_current_public_ip()
    
    # 2. 设置白名单
    if not xq.set_whitelist(my_ip):
        log("无法授权当前 IP，任务终止", "ERROR")
        return

    # 3. 获取代理 IP
    proxies = xq.get_proxy(count=1)
    if not proxies:
        log("未能获取到有效代理，任务终止", "ERROR")
        return
    proxy_server = proxies[0]
    log(f"使用代理: {proxy_server}", "PROXY")

    # 4. 获取京东账号/VID 信息
    account_info = get_decoded_account()
    if not account_info:
        log("未找到可用的 PROXY_INFO 账号信息", "ERROR")
        return
    
    # 假设 vid.json 在同目录下
    vid_file = "vid.json"
    if not os.path.exists(vid_file):
        log("vid.json 不存在", "ERROR")
        return
    with open(vid_file, "r") as f:
        vender_ids = json.load(f)

    # 5. 启动 Playwright 流程
    with sync_playwright() as p:
        try:
            # 将携趣代理注入 Playwright
            browser = p.chromium.launch(
                headless=True,
                proxy={"server": proxy_server}
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
                viewport={'width': 390, 'height': 844}
            )

            for vid in vender_ids:
                page = context.new_page()
                try:
                    log(f"正在处理店铺: {vid}", "INFO")
                    page.goto(f"https://shop.m.jd.com/shop/home?venderId={vid}", wait_until="networkidle", timeout=30000)
                    
                    # 执行注入式 Fetch
                    fetch_script = f"""
                    async () => {{
                        const res = await fetch("https://api.m.jd.com/client.action", {{
                            "method": "POST",
                            "headers": {{ "content-type": "application/x-www-form-urlencoded" }},
                            "body": "functionId=whx_getShopHomeActivityInfo&body=%7B%22venderId%22%3A%22{vid}%22%2C%22source%22%3A%22m-shop%22%7D&appid=shop_m_jd_com&clientVersion=11.0.0&client=wh5"
                        }});
                        return await res.json();
                    }}
                    """
                    res_json = page.evaluate(fetch_script)

                    if res_json and res_json.get("code") == "0":
                        isv_url = res_json.get("result", {}).get("signStatus", {}).get("isvUrl", "")
                        if TARGET_PATTERN in isv_url:
                            token = re.search(r'token=([^&]+)', isv_url).group(1) if "token=" in isv_url else "N/A"
                            log(f"🎯 命中店铺 {vid} | Token: {token}", "SUCCESS")
                        else:
                            log(f"店铺 {vid} 无目标活动", "INFO")
                    else:
                        log(f"店铺 {vid} 请求失败", "WARN")

                except Exception as e:
                    log(f"处理店铺 {vid} 异常: {e}", "ERROR")
                finally:
                    page.close()
                
                time.sleep(random.uniform(1, 3))

            browser.close()
        finally:
            # 6. 任务结束，清理白名单
            xq.del_whitelist(my_ip)
            log("清理白名单完成，任务结束", "INFO")

if __name__ == "__main__":
    run_task()
