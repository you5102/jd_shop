import os
import json
import time
import re
import base64
import sys
import requests
from playwright.sync_api import sync_playwright

# --- 兼容性导入 playwright_stealth ---
try:
    import playwright_stealth
    # 统一调用接口
    def apply_stealth(page):
        try:
            playwright_stealth.stealth_sync(page)
        except Exception:
            pass
except ImportError:
    def apply_stealth(page):
        pass

# ================= 配置区 =================
TARGET_PATTERN = "2PAAf74aG3D61qvfKUM5dxUssJQ9"
PROXY_REFRESH_SECONDS = 45    # 刷新频率（必须 > 30s）
RUN_DURATION_MINUTES = 5      # 脚本运行总时长
MAX_CONSECUTIVE_ERRORS = 3     # 连续核心报错停止阈值

# --- SOCKS5 代理配置 ---
# 建议在 GitHub Secrets 中配置变量 SOCKS5_PROXY
# 格式: socks5://user:pass@host:port 或 socks5://host:port
SOCKS5_PROXY = os.environ.get("SOCKS5_PROXY") or "socks5://127.0.0.1:1080"
# =========================================

class XieQuManager:
    def __init__(self, uid, ukey, vkey, socks_proxy):
        self.uid = uid
        self.ukey = ukey
        self.vkey = vkey
        self.socks_proxy = socks_proxy
        self.last_api_time = 0 
        self.min_interval = 32
        
        # 初始化带 SOCKS5 代理的会话，用于请求携趣 API
        self.session = requests.Session()
        if self.socks_proxy:
            self.session.proxies = {
                'http': self.socks_proxy,
                'https': self.socks_proxy
            }
            self.log(f"已启用 SOCKS5 中转代理: {self.socks_proxy}", "INFO")

    def log(self, msg, level="INFO"):
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        icons = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️", "PROXY": "🌐", "TIMER": "⏱️"}
        print(f"[{timestamp}] {icons.get(level, '•')} {msg}", flush=True)

    def _wait_for_cooldown(self):
        """确保 API 调用间隔不小于 30 秒，防止 111 Connection Refused"""
        now = time.time()
        elapsed = now - self.last_api_time
        if elapsed < self.min_interval:
            wait_sec = self.min_interval - elapsed
            self.log(f"API 冷却中，等待 {wait_sec:.1f} 秒...", "TIMER")
            time.sleep(wait_sec)
        self.last_api_time = time.time()

    def check_api_link(self):
        """通过 SOCKS5 代理自检与携趣 API 的连通性"""
        self.log(f"正在自检 API 链路...", "INFO")
        try:
            # 尝试访问携趣接口域名
            res = self.session.get("http://api.xiequ.cn/VAD/GetIp.aspx", timeout=12)
            return True
        except Exception as e:
            self.log(f"链路故障（无法通过 SOCKS5 连接携趣）: {e}", "ERROR")
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
                self.log(f"白名单设置成功: {ip}", "SUCCESS")
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
                p_list = [f"http://{item['IP']}:{item['Port']}" for item in data.get("data", [])]
                self.log(f"提取代理成功: {p_list[0]}", "SUCCESS")
                return p_list
            self.log(f"提取代理失败: {data.get('msg')}", "WARN")
            return []
        except Exception as e:
            self.log(f"通过 SOCKS5 获取代理异常: {e}", "ERROR")
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
    except Exception:
        return None

def run_task():
    account = get_decoded_account()
    if not account:
        print("❌ 错误：未配置或无效的 PROXY_INFO")
        return

    xq = XieQuManager(
        account.get("uid"), 
        account.get("ukey"), 
        account.get("vkey"), 
        socks_proxy=SOCKS5_PROXY
    )
    
    if not xq.check_api_link():
        sys.exit(1)

    vid_file = "vid.json"
    if not os.path.exists(vid_file):
        print("❌ vid.json 不存在")
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
                    xq.log("时间到，脚本停止", "TIMER")
                    break

                # 代理环境切换逻辑
                if now - last_proxy_time > PROXY_REFRESH_SECONDS:
                    if browser: browser.close()
                    if current_white_ip: xq.del_whitelist(current_white_ip)
                    
                    xq.log("正在更换代理 IP...", "PROXY")
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
                                xq.log(f"新环境就绪: {proxies[0]}", "SUCCESS")
                                success = True
                                consecutive_errors = 0
                                last_proxy_time = time.time()
                            except Exception as e:
                                xq.log(f"启动浏览器失败: {e}", "ERROR")

                    if not success:
                        consecutive_errors += 1
                        xq.log(f"连续失败 ({consecutive_errors}/{MAX_CONSECUTIVE_ERRORS})", "ERROR")
                        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                            xq.log("连续失败次数过多，终止程序", "ERROR")
                            sys.exit(1)
                        continue

                # 页面业务逻辑
                page = context.new_page()
                apply_stealth(page) # 使用修正后的 Stealth 调用
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
                            xq.log(f"🎯 命中店铺 {vid} | Token: {token}", "SUCCESS")
                        else:
                            xq.log(f"店铺 {vid} 无活动", "INFO")
                    else:
                        xq.log(f"店铺 {vid} 数据获取异常", "WARN")

                except Exception as e:
                    xq.log(f"处理店铺 {vid} 异常: {e}", "WARN")
                finally:
                    page.close()
                
                time.sleep(1.5)

        finally:
            if browser: browser.close()
            if current_white_ip: xq.del_whitelist(current_white_ip)
            xq.log("任务结束，清理完成。", "INFO")

if __name__ == "__main__":
    run_task()
