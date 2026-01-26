import os
import json
import time
import re
import base64
import sys
import requests
from playwright.sync_api import sync_playwright

# ================= 配置区 =================
TARGET_PATTERN = "2PAAf74aG3D61qvfKUM5dxUssJQ9"
PROXY_REFRESH_SECONDS = 40  # 建议略大于30，给业务留出执行时间
RUN_DURATION_MINUTES = 5    # 设定运行时长（分钟）
MAX_CONSECUTIVE_ERRORS = 3   # 连续报错最大次数
# =========================================

class XieQuManager:
    def __init__(self, uid, ukey, vkey):
        self.uid = uid
        self.ukey = ukey
        self.vkey = vkey
        self.base_url = "http://op.xiequ.cn"
        self.last_api_time = 0 
        self.min_interval = 31  # 严格限制间隔时间（秒）

    def log(self, msg, level="INFO"):
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        icons = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️", "PROXY": "🌐", "TIMER": "⏱️"}
        print(f"[{timestamp}] {icons.get(level, '•')} {msg}", flush=True)

    def _wait_for_cooldown(self):
        """强制 API 冷却逻辑，防止 Connection Refused"""
        now = time.time()
        elapsed = now - self.last_api_time
        if elapsed < self.min_interval:
            wait_sec = self.min_interval - elapsed
            self.log(f"API 冷却中，需等待 {wait_sec:.1f} 秒...", "TIMER")
            time.sleep(wait_sec)
        self.last_api_time = time.time()

    def get_current_public_ip(self):
        try:
            return requests.get("http://ifconfig.me/ip", timeout=5).text.strip()
        except:
            return requests.get("http://api.ipify.org", timeout=5).text.strip()

    def set_whitelist(self, ip):
        self._wait_for_cooldown()
        url = f"{self.base_url}/IpWhiteList.aspx?uid={self.uid}&ukey={self.ukey}&act=add&ip={ip}&meno=1"
        try:
            res = requests.get(url, timeout=10)
            if "success" in res.text.lower() or "已存在" in res.text:
                self.log(f"白名单设置成功: {ip}", "SUCCESS")
                time.sleep(5)  # 额外给服务器 5 秒同步时间
                return True
            self.log(f"白名单设置失败: {res.text}", "ERROR")
            return False
        except Exception as e:
            self.log(f"设置白名单异常: {e}", "ERROR")
            return False

    def del_whitelist(self, ip):
        if not ip: return
        self._wait_for_cooldown()
        url = f"{self.base_url}/IpWhiteList.aspx?uid={self.uid}&ukey={self.ukey}&act=del&ip={ip}"
        try:
            requests.get(url, timeout=5)
            self.log(f"清理白名单完成: {ip}", "INFO")
        except:
            pass

    def get_proxy(self, count=1):
        self._wait_for_cooldown()
        url = f"http://api.xiequ.cn/VAD/GetIp.aspx?act=get&uid={self.uid}&vkey={self.vkey}&num={count}&time=30&plat=0&re=1&type=0&so=1&ow=1&spl=1&addr=&db=1"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code != 200:
                self.log(f"代理接口响应 HTTP {res.status_code}", "ERROR")
                return []
            data = res.json()
            if data.get("code") == 0:
                return [f"http://{item['IP']}:{item['Port']}" for item in data.get("data", [])]
            self.log(f"获取代理失败: {data.get('msg')}", "ERROR")
            return []
        except Exception as e:
            self.log(f"获取代理接口异常 (可能被拒连): {e}", "ERROR")
            return []

def get_decoded_account():
    try:
        raw_data = os.environ.get("PROXY_INFO", "")
        if not raw_data: return None
        decoded_bytes = base64.b64decode(raw_data)
        accounts = json.loads(decoded_bytes.decode('utf-8'))
        return accounts[0] if isinstance(accounts, list) else accounts
    except Exception as e:
        print(f"账号解码失败: {e}")
        return None

def run_task():
    account = get_decoded_account()
    if not account:
        print("❌ 未获取到有效代理配置")
        return

    xq = XieQuManager(account.get("uid"), account.get("ukey"), account.get("vkey"))
    
    vid_file = "vid.json"
    if not os.path.exists(vid_file):
        xq.log("vid.json 不存在", "ERROR")
        return
    with open(vid_file, "r") as f:
        vender_ids = json.load(f)

    script_start_time = time.time()
    last_proxy_time = 0
    browser, context, current_white_ip = None, None, None
    consecutive_errors = 0

    xq.log(f"任务启动，设定时长: {RUN_DURATION_MINUTES} 分钟", "TIMER")

    with sync_playwright() as p:
        try:
            for vid in vender_ids:
                now = time.time()
                
                # 1. 时长检查
                if (now - script_start_time) / 60 >= RUN_DURATION_MINUTES:
                    xq.log("达到预设时间，脚本准备停止", "TIMER")
                    break

                # 2. 代理切换逻辑
                if now - last_proxy_time > PROXY_REFRESH_SECONDS:
                    if browser: browser.close()
                    if current_white_ip: xq.del_whitelist(current_white_ip)
                    
                    xq.log("正在尝试切换代理环境...", "PROXY")
                    current_white_ip = xq.get_current_public_ip()
                    
                    if xq.set_whitelist(current_white_ip):
                        proxies = xq.get_proxy(count=1)
                        if proxies:
                            try:
                                browser = p.chromium.launch(headless=True, proxy={"server": proxies[0]})
                                context = browser.new_context(
                                    user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
                                    viewport={'width': 390, 'height': 844}
                                )
                                xq.log(f"成功进入新代理环境: {proxies[0]}", "SUCCESS")
                                consecutive_errors = 0 # 重置连续错误
                                last_proxy_time = time.time()
                            except Exception as e:
                                xq.log(f"浏览器启动失败: {e}", "ERROR")
                                browser = None
                        else:
                            browser = None
                    else:
                        browser = None

                    # 核心报错处理：如果环境创建失败
                    if not browser:
                        consecutive_errors += 1
                        xq.log(f"核心操作失败 ({consecutive_errors}/{MAX_CONSECUTIVE_ERRORS})", "ERROR")
                        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                            xq.log("连续 3 次核心操作失败，终止程序以保护账号/IP", "ERROR")
                            sys.exit(1)
                        continue

                # 3. 业务逻辑
                page = context.new_page()
                try:
                    xq.log(f"扫描店铺: {vid}", "INFO")
                    page.goto(f"https://shop.m.jd.com/shop/home?venderId={vid}", wait_until="networkidle", timeout=15000)
                    
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
                            xq.log(f"🎯 命中店铺 {vid} | Token: {token}", "SUCCESS")
                        else:
                            xq.log(f"店铺 {vid} 无目标活动", "INFO")
                    else:
                        xq.log(f"店铺 {vid} 接口返回异常", "WARN")

                except Exception as e:
                    xq.log(f"处理店铺 {vid} 异常: {e}", "WARN")
                finally:
                    page.close()
                
                time.sleep(1) # 店铺间基础停顿

        finally:
            if browser: browser.close()
            if current_white_ip: xq.del_whitelist(current_white_ip)
            xq.log(f"全部任务结束，清理完成。", "INFO")

if __name__ == "__main__":
    run_task()
