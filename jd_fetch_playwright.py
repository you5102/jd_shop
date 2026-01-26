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
PROXY_REFRESH_SECONDS = 45    # 刷新频率
RUN_DURATION_MINUTES = 5      # 脚本运行总时长
MAX_CONSECUTIVE_ERRORS = 3     # 连续核心报错停止阈值

# --- SOCKS5 代理配置 ---
# 优先从环境变量获取，如果没有则使用脚本内填写的
# 格式: socks5://user:pass@host:port 或 socks5://host:port
SOCKS5_PROXY = os.environ.get("SOCKS5_PROXY") or "socks5://你的IP:端口"
# =========================================

class XieQuManager:
    def __init__(self, uid, ukey, vkey, socks_proxy):
        self.uid = uid
        self.ukey = ukey
        self.vkey = vkey
        self.socks_proxy = socks_proxy
        self.last_api_time = 0 
        self.min_interval = 32
        
        # 初始化带 SOCKS5 代理的会话
        self.session = requests.Session()
        if self.socks_proxy:
            self.session.proxies = {
                'http': self.socks_proxy,
                'https': self.socks_proxy
            }

    def log(self, msg, level="INFO"):
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        icons = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️", "PROXY": "🌐", "TIMER": "⏱️"}
        print(f"[{timestamp}] {icons.get(level, '•')} {msg}", flush=True)

    def _wait_for_cooldown(self):
        """确保 API 调用间隔不小于 30 秒"""
        now = time.time()
        elapsed = now - self.last_api_time
        if elapsed < self.min_interval:
            wait_sec = self.min_interval - elapsed
            self.log(f"API 冷却中，等待 {wait_sec:.1f} 秒...", "TIMER")
            time.sleep(wait_sec)
        self.last_api_time = time.time()

    def check_api_link(self):
        """通过 SOCKS5 代理自检与携趣 API 的连通性"""
        self.log(f"正在通过中转代理检测连通性...", "INFO")
        try:
            # 尝试访问携趣接口
            res = self.session.get("http://api.xiequ.cn/VAD/GetIp.aspx", timeout=12)
            return True
        except Exception as e:
            self.log(f"中转链路故障，无法连接携趣 API: {e}", "ERROR")
            return False

    def get_current_public_ip(self):
        """获取 GitHub 运行机的真实公网 IP（用于设置白名单）"""
        try:
            # 强制不使用代理获取本机真实 IP
            return requests.get("http://ifconfig.me/ip", timeout=5, proxies={}).text.strip()
        except:
            return requests.get("http://api.ipify.org", timeout=5, proxies={}).text.strip()

    def set_whitelist(self, ip):
        self._wait_for_cooldown()
        url = f"http://op.xiequ.cn/IpWhiteList.aspx?uid={self.uid}&ukey={self.ukey}&act=add&ip={ip}&meno=1"
        try:
            res = self.session.get(url, timeout=15)
            if "success" in res.text.lower() or "已存在" in res.text:
                self.log(f"白名单设置成功 (via SOCKS5): {ip}", "SUCCESS")
                time.sleep(5) # 给服务器同步时间
                return True
            self.log(f"白名单设置失败: {res.text}", "ERROR")
            return False
        except Exception as e:
            self.log(f"中转请求白名单异常: {e}", "ERROR")
            return False

    def get_proxy(self, count=1):
        self._wait_for_cooldown()
        url = f"http://api.xiequ.cn/VAD/GetIp.aspx?act=get&uid={self.uid}&vkey={self.vkey}&num={count}&time=30&plat=0&re=1&type=0&so=1&ow=1&spl=1&addr=&db=1"
        try:
            res = self.session.get(url, timeout=15)
            data = res.json()
            if data.get("code") == 0:
                return [f"http://{item['IP']}:{item['Port']}" for item in data.get("data", [])]
            self.log(f"API 返回错误: {data.get('msg')}", "WARN")
            return []
        except Exception as e:
            self.log(f"中转提取代理异常: {e}", "ERROR")
            return []

    def del_whitelist(self, ip):
        if not ip: return
        self._wait_for_cooldown()
        url = f"http://op.xiequ.cn/IpWhiteList.aspx?uid={self.uid}&ukey={self.ukey}&act=del&ip={ip}"
        try:
            self.session.get(url, timeout=10)
            self.log(f"清理白名单完成: {ip}", "INFO")
        except:
            pass

def get_decoded_account():
    try:
        raw_data = os.environ.get("PROXY_INFO", "")
        if not raw_data: return None
        decoded_bytes = base64.b64decode(raw_data)
        accounts = json.loads(decoded_bytes.decode('utf-8'))
        return accounts[0] if isinstance(accounts, list) else accounts
    except Exception as e:
        print(f"账号解析失败: {e}")
        return None

def run_task():
    account = get_decoded_account()
    if not account:
        print("❌ 错误：未配置 PROXY_INFO 环境变量")
        return

    # 初始化管理器
    xq = XieQuManager(
        account.get("uid"), 
        account.get("ukey"), 
        account.get("vkey"), 
        socks_proxy=SOCKS5_PROXY
    )
    
    # 1. 链路预检
    if not xq.check_api_link():
        sys.exit(1)

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

    with sync_playwright() as p:
        try:
            for vid in vender_ids:
                now = time.time()
                if (now - script_start_time) / 60 >= RUN_DURATION_MINUTES:
                    xq.log("运行时间达上限，退出...", "TIMER")
                    break

                # 2. 核心：代理环境切换
                if now - last_proxy_time > PROXY_REFRESH_SECONDS:
                    if browser: browser.close()
                    if current_white_ip: xq.del_whitelist(current_white_ip)
                    
                    xq.log("正在通过中转代理更换环境...", "PROXY")
                    current_white_ip = xq.get_current_public_ip()
                    
                    success = False
                    if xq.set_whitelist(current_white_ip):
                        proxies = xq.get_proxy(count=1)
                        if proxies:
                            try:
                                # 注意：浏览器运行走的是刚提取的携趣代理，不走 SOCKS5 中转
                                browser = p.chromium.launch(headless=True, proxy={"server": proxies[0]})
                                context = browser.new_context(
                                    user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
                                    viewport={'width': 390, 'height': 844}
                                )
                                xq.log(f"新代理环境已就绪: {proxies[0]}", "SUCCESS")
                                success = True
                                consecutive_errors = 0
                                last_proxy_time = time.time()
                            except Exception as e:
                                xq.log(f"浏览器启动失败: {e}", "ERROR")

                    if not success:
                        consecutive_errors += 1
                        xq.log(f"环境创建连续失败 ({consecutive_errors}/{MAX_CONSECUTIVE_ERRORS})", "ERROR")
                        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                            xq.log("连续多次核心失败，停止脚本以自我保护。", "ERROR")
                            sys.exit(1)
                        continue

                # 3. 页面业务逻辑
                page = context.new_page()
                stealth_sync(page)
                try:
                    xq.log(f"正在扫描店铺: {vid}", "INFO")
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
                            xq.log(f"🎯 命中目标! 店铺: {vid} | Token: {token}", "SUCCESS")
                        else:
                            xq.log(f"店铺 {vid} 无活动", "INFO")
                    else:
                        xq.log(f"店铺 {vid} 接口请求未通过", "WARN")

                except Exception as e:
                    xq.log(f"处理店铺 {vid} 时发生页面异常: {e}", "WARN")
                finally:
                    page.close()
                
                time.sleep(1.5)

        finally:
            if browser: browser.close()
            if current_white_ip: xq.del_whitelist(current_white_ip)
            xq.log("脚本执行结束。", "INFO")

if __name__ == "__main__":
    run_task()
