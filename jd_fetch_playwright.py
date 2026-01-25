import json
import time
import re
import os
import random
import sys
from playwright.sync_api import sync_playwright

# ================= 配置区 =================
DEBUG_MODE = False  
MAX_CONTINUOUS_ERRORS = 5
VID_FILE = "vid.json"
TARGET_PATTERN = "2PAAf74aG3D61qvfKUM5dxUssJQ9"
# =========================================

def log(msg, level="INFO"):
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    icons = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️", "DEBUG": "🔍"}
    print(f"[{timestamp}] {icons.get(level, '•')} {msg}", flush=True)

def run_task():
    log("🚀 Playwright 京东注入式任务启动", "INFO")
    
    if not os.path.exists(VID_FILE):
        log(f"找不到配置文件: {VID_FILE}", "ERROR")
        return

    with open(VID_FILE, "r") as f:
        vender_ids = json.load(f)

    error_count = 0

    with sync_playwright() as p:
        # 启动浏览器，headless=True 表示无头模式（Actions 运行必须）
        browser = p.chromium.launch(headless=True)
        # 模拟移动端环境
        context = browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            viewport={'width': 390, 'height': 844}
        )

        for vid in vender_ids:
            if error_count >= MAX_CONTINUOUS_ERRORS:
                log(f"已连续报错 {MAX_CONTINUOUS_ERRORS} 次，熔断退出。", "ERROR")
                browser.close()
                sys.exit(1)

            log(f"正在处理店铺: {vid}", "INFO")

            if DEBUG_MODE:
                log(f"[测试模式] 跳过请求 {vid}", "DEBUG")
                continue

            page = context.new_page()
            try:
                # 1. 访问店铺首页，建立上下文环境
                shop_url = f"https://shop.m.jd.com/shop/home?venderId={vid}"
                page.goto(shop_url, wait_until="networkidle", timeout=60000)
                
                # 2. 在页面内执行 fetch
                # 使用 JavaScript 动态构造 body 里的 venderId
                fetch_script = f"""
                async () => {{
                    const response = await fetch("https://api.m.jd.com/client.action", {{
                        "method": "POST",
                        "headers": {{
                            "content-type": "application/x-www-form-urlencoded",
                            "x-rp-client": "h5_1.0.0"
                        }},
                        "body": "functionId=whx_getShopHomeActivityInfo&body=%7B%22venderId%22%3A%22{vid}%22%2C%22source%22%3A%22m-shop%22%7D&appid=shop_m_jd_com&clientVersion=11.0.0&client=wh5"
                    }});
                    return await response.json();
                }}
                """
                
                res_json = page.evaluate(fetch_script)

                if not res_json or res_json.get("code") != "0":
                    error_count += 1
                    log(f"接口返回异常: {res_json.get('msg', '未知')}", "WARN")
                    page.close()
                    continue

                # 成功则清零
                error_count = 0
                
                isv_url = res_json.get("result", {}).get("signStatus", {}).get("isvUrl", "")
                if TARGET_PATTERN in isv_url:
                    token_match = re.search(r'token=([^&]+)', isv_url)
                    token = token_match.group(1) if token_match else "None"
                    log(f"✅ 匹配成功! Token: {token}", "SUCCESS")
                else:
                    log(f"VID {vid} 无目标活动", "INFO")

            except Exception as e:
                error_count += 1
                log(f"操作异常: {e}", "ERROR")
            
            finally:
                page.close()
                time.sleep(random.uniform(2, 5))

        browser.close()
    log("🏁 任务结束", "SUCCESS")

if __name__ == "__main__":
    run_task()
