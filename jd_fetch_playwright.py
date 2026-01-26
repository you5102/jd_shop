import os
import json
import time
import re
import base64
import sys
import requests
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

# ================= 配置区 =================
TARGET_PATTERN = "2PAAf74aG3D61qvfKUM5dxUssJQ9"
PROXY_REFRESH_SECONDS = 45  # 刷新频率（必须 > 30s）
RUN_DURATION_MINUTES = 5    # 脚本运行总时长
MAX_CONSECUTIVE_ERRORS = 3   # 连续核心报错停止阈值
# =========================================

class XieQuManager:
    def __init__(self, uid, ukey, vkey):
        self.uid = uid
        self.ukey = ukey
        self.vkey = vkey
        self.base_url = "http://op.xiequ.cn"
        self.last_api_time = 0 
        self.min_interval = 32  # 强制 API 间隔 32 秒（留 2s 缓冲）

    def log(self, msg, level="INFO"):
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        icons = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️", "PROXY": "🌐", "TIMER": "⏱️"}
        print(f"[{timestamp}] {icons.get(level, '•')} {msg}", flush=True)

    def _wait_for_cooldown(self):
        """核心：确保携趣 API 调用不违反频率限制"""
        now = time.time()
        elapsed = now - self.last_api_time
        if elapsed < self.min_interval:
            wait_sec = self.min_interval - elapsed
            self.log(f"API 冷却中，需等待 {wait_sec:.1f} 秒以免触发封锁...", "TIMER")
            time.sleep(wait_sec)
        self.last_api_time = time.time()

    def check_api_link(self):
        """自检链路，防止因为被拒连而盲目重试"""
        try:
            res = requests.get(f"{self.base_url}/IpWhiteList.aspx", timeout=5)
            return True
        except requests.exceptions.ConnectionError:
            self.log("链路检测失败：携趣 API 拒绝了 GitHub 的连接。请重新运行任务。", "ERROR")
            return False

    def get_current_public_ip(self):
        """获取 GitHub 运行机的公网 IP"""
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
                time.sleep(5)  # 设置成功后额外给后端 5 秒同步时间
                return True
            self.log(f"白名单设置失败: {res.text}", "ERROR")
            return False
        except Exception as e:
            self.log(f"请求白名单接口异常: {e}", "ERROR")
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
                self.log(f"代理接口 HTTP 状态异常: {res.status_code}", "ERROR")
                return []
            data = res.json()
            if data.get("code") == 0:
                return [f"http://{item['IP']}:{item['Port']}" for item in data.get("data", [])]
            self.log(f"获取代理失败: {data.get('msg')}", "WARN")
            return []
        except Exception as e:
            self.log(f"获取代理 API 网络错误 (可能被拒连): {e}", "ERROR")
            return []

def get_decoded_account():
    try:
        raw_data = os.environ.get("PROXY_INFO", "")
        if not raw_data: return None
        decoded_bytes = base64.b64decode(raw_data)
        accounts = json.loads(decoded_bytes.decode('utf-8'))
        return accounts[0] if isinstance(accounts, list) else accounts
    except Exception as e:
        print(f"账号信息解码异常: {e}")
        return None

def run_task():
    account = get_decoded_account()
    if not account:
        print("❌ 错误：环境变量 PROXY_INFO 为空或无效。")
        return

    xq = XieQuManager(account.get("uid"), account.get("ukey"), account.get("vkey"))
    
    # 链路预检
    if not xq.check_api_link():
        sys.exit(1)

    vid_file = "vid.json"
    if not os.path.exists(vid_file):
        xq.log("vid.json 文件缺失", "ERROR")
        return
    with open(vid_file, "r") as f:
        vender_ids = json.load(f)

    script_start_time = time.time()
    last_proxy_time = 0
    browser, context, current_white_ip = None, None, None
    consecutive_errors = 0

    xq.log(f"任务启动，预计运行 {RUN_DURATION_MINUTES} 分钟", "TIMER")

    with sync_playwright() as p:
        try:
            for vid in vender_ids:
                now = time.time()
                
                # 1. 运行超时检查
                if (now - script_start_time) / 60 >= RUN_DURATION_MINUTES:
                    xq.log("运行时间已达上限，安全退出...", "TIMER")
                    break

                # 2. 核心：代理/白名单切换逻辑
                if now - last_proxy_time > PROXY_REFRESH_SECONDS:
                    if browser: browser.close()
                    if current_white_ip: xq.del_whitelist(current_white_ip)
                    
                    xq.log("尝试获取并配置新代理 IP...", "PROXY")
                    current_white_ip = xq.get_current_public_ip()
                    
                    success = False
                    if xq.set_whitelist(current_white_ip):
                        proxies = xq.get_proxy(count=1)
                        if proxies:
                            try:
                                browser = p.chromium.launch(headless=True, proxy={"server": proxies[0]})
                                context = browser.new_context(
                                    user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
                                    viewport={'width': 390, 'height': 844}
                                )
                                xq.log(f"代理环境就绪: {proxies[0]}", "SUCCESS")
                                success = True
                                consecutive_errors = 0
                                last_proxy_time = time.time()
                            except Exception as e:
                                xq.log(f"浏览器环境初始化失败: {e}", "ERROR")

                    if not success:
                        consecutive_errors += 1
                        xq.log(f"连续核心失败计数: {consecutive_errors}/{MAX_CONSECUTIVE_ERRORS}", "ERROR")
                        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                            xq.log("连续多次 API 异常，停止运行以防 IP/账号风险", "ERROR")
                            sys.exit(1)
                        continue

                # 3. 业务逻辑处理
                page = context.new_page()
                stealth_sync(page) # 隐藏 Playwright 特征
                try:
                    xq.log(f"正在扫描: {vid}", "INFO")
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
                            xq.log(f"店铺 {vid} 未检测到目标活动", "INFO")
                    else:
                        xq.log(f"店铺 {vid} 响应数据为空（可能 IP 被京东拦截）", "WARN")

                except Exception as e:
                    xq.log(f"页面操作异常: {vid} | {e}", "WARN")
                finally:
                    page.close()
                
                time.sleep(1.5) # 店铺间微小停顿

        finally:
            if browser: browser.close()
            if current_white_ip: xq.del_whitelist(current_white_ip)
            xq.log("脚本执行完毕，资源已安全回收。", "INFO")

if __name__ == "__main__":
    run_task()
