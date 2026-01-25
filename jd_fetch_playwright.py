import os
import json
import time
import re
import random
import base64
import sys
from playwright.sync_api import sync_playwright
from proxy import XieQuManager

# ================= 配置区 =================
TARGET_PATTERN = "2PAAf74aG3D61qvfKUM5dxUssJQ9"
PROXY_REFRESH_SECONDS = 25  # 每25秒更换一次IP
RUN_DURATION_MINUTES = 10   # 设定运行时长（分钟），到时间后自动停止
# =========================================

def log(msg, level="INFO"):
    timestamp = time.strftime("%H:%M:%S", time.localtime())
    icons = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️", "PROXY": "🌐", "TIMER": "⏱️"}
    print(f"[{timestamp}] {icons.get(level, '•')} {msg}", flush=True)

def get_decoded_account():
    """从环境变量读取并解码账号信息"""
    try:
        raw_data = os.environ.get("PROXY_INFO", "")
        if not raw_data: return None
        decoded_bytes = base64.b64decode(raw_data)
        accounts = json.loads(decoded_bytes.decode('utf-8'))
        return accounts[0] if isinstance(accounts, list) else accounts
    except Exception as e:
        log(f"账号解码失败: {e}", "ERROR")
        return None

def create_new_proxy_context(p, xq):
    """获取新IP，设白名单，并返回新的浏览器上下文"""
    my_ip = xq.get_current_public_ip()
    # 设置白名单
    if not xq.set_whitelist(my_ip):
        log("白名单授权失败", "ERROR")
        return None, None, my_ip

    # 获取代理 IP
    proxies = xq.get_proxy(count=1)
    if not proxies:
        log("未能获取到新代理", "ERROR")
        return None, None, my_ip
    
    proxy_server = proxies[0]
    log(f"🔄 已更换新代理: {proxy_server}", "PROXY")

    browser = p.chromium.launch(headless=True, proxy={"server": proxy_server})
    context = browser.new_context(
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        viewport={'width': 390, 'height': 844}
    )
    return browser, context, my_ip

def run_task():
    PROXY_INFO = get_decoded_account()
    if not PROXY_INFO:
        log("未获取到代理配置信息", "ERROR")
        return

    xq = XieQuManager(PROXY_INFO.get("uid"), PROXY_INFO.get("ukey"), PROXY_INFO.get("vkey"))
    
    vid_file = "vid.json"
    if not os.path.exists(vid_file):
        log("vid.json 不存在", "ERROR")
        return
    with open(vid_file, "r") as f:
        vender_ids = json.load(f)

    # 记录脚本开始时间
    script_start_time = time.time()
    last_proxy_time = 0
    browser = None
    context = None
    current_white_ip = None

    log(f"设定运行时长为: {RUN_DURATION_MINUTES} 分钟", "TIMER")

    with sync_playwright() as p:
        try:
            for vid in vender_ids:
                now = time.time()
                
                # --- 1. 运行时长检查 ---
                elapsed_minutes = (now - script_start_time) / 60
                if elapsed_minutes >= RUN_DURATION_MINUTES:
                    log(f"已达到设定时长 ({RUN_DURATION_MINUTES}分钟)，脚本准备停止...", "TIMER")
                    break

                # --- 2. 检查是否需要更换代理 (每25秒) ---
                if now - last_proxy_time > PROXY_REFRESH_SECONDS:
                    if browser:
                        browser.close()
                    if current_white_ip:
                        xq.del_whitelist(current_white_ip)
                    
                    browser, context, current_white_ip = create_new_proxy_context(p, xq)
                    if not browser:
                        log("环境创建失败，尝试跳过此轮", "ERROR")
                        continue
                    last_proxy_time = time.time()

                # --- 3. 执行业务逻辑 ---
                page = context.new_page()
                try:
                    log(f"正在处理店铺: {vid} (已运行 {elapsed_minutes:.1f}min)", "INFO")
                    page.goto(f"https://shop.m.jd.com/shop/home?venderId={vid}", wait_until="networkidle", timeout=20000)
                    
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
                        log(f"店铺 {vid} 请求失败 (可能代理失效)", "WARN")

                except Exception as e:
                    log(f"店铺 {vid} 访问异常: {e}", "ERROR")
                finally:
                    page.close()
                
                time.sleep(1)

        finally:
            # 无论是因为跑完列表还是时间到了，都执行清理
            if browser: browser.close()
            if current_white_ip: xq.del_whitelist(current_white_ip)
            total_time = (time.time() - script_start_time) / 60
            log(f"任务结束，总运行时间: {total_time:.1f} 分钟", "INFO")

if __name__ == "__main__":
    run_task()
