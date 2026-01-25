import requests
import time
import sys

class XieQuManager:
    def __init__(self, uid, ukey, vkey):
        """
        :param uid: 携趣用户ID
        :param ukey: 携趣用户Key
        :param vkey: 携趣用户Key
        """
        self.uid = uid
        self.ukey = ukey
        self.vkey = vkey
        self.base_url = "http://op.xiequ.cn"

    def log(self, msg, level="INFO"):
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        icon = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌"}.get(level, "•")
        print(f"[{timestamp}] {icon} {msg}", flush=True)

    def set_whitelist(self, ip):
        """添加当前机器 IP 到白名单"""
        url = f"{self.base_url}/IpWhiteList.aspx?uid={self.uid}&ukey={self.ukey}&act=add&ip={ip}&meno=1#"
        #self.log(f"添加白名单 url: {url}", "INFO")
        try:
            res = requests.get(url, timeout=10)
            self.log(f"添加白名单 res: {res}", "INFO")
            if "success" in res.text.lower() or "已存在" in res.text:
                self.log(f"白名单设置成功或已存在: {ip}", "SUCCESS")
                return True
            else:
                self.log(f"白名单设置失败: {res.text}", "ERROR")
                return False
        except Exception as e:
            self.log(f"请求白名单接口异常: {e}", "ERROR")
            return False

    def del_whitelist(self, ip):
        """从白名单中删除指定 IP"""
        url = f"{self.base_url}/IpWhiteList.aspx?uid={self.uid}&ukey={self.ukey}&act=del&ip={ip}"

        try:
            res = requests.get(url, timeout=10)
            self.log(f"删除白名单响应: {res.text}", "INFO")
            return True
        except Exception as e:
            self.log(f"删除白名单异常: {e}", "ERROR")
            return False

    def get_proxy(self, count=1, protocol="http"):
        """
        获取代理 IP
        :param count: 获取数量
        :param protocol: 协议类型 (http, https, socks5)
        """
        # 注意：这里的 lineID, pt, dev_type 等参数需根据你购买的套餐 API 链接调整
        # 下面是一个常见的获取接口示例
        url = f"http://api.xiequ.cn/VAD/GetIp.aspx?act=get&uid={self.uid}&vkey={self.ukey}&num={count}&time=30&plat=0&re=1&type=0&so=1&ow=1&spl=1&addr=&db=1"
        try:
            res = requests.get(url, timeout=10)
            data = res.json()

            if data.get("code") == 0:
                proxy_list = []
                for item in data.get("data", []):
                    ip_port = f"{item['IP']}:{item['Port']}"
                    proxy_list.append(f"{protocol}://{ip_port}")
                self.log(f"成功获取 {len(proxy_list)} 个代理 IP", "SUCCESS")
                return proxy_list
            else:
                self.log(f"获取代理失败: {data.get('msg')}", "ERROR")
                return []
        except Exception as e:
            self.log(f"获取代理接口异常: {e}", "ERROR")
            return []

    def get_current_public_ip(self):
        """获取当前机器的公网 IP"""
        try:
            return requests.get("http://ifconfig.me/ip", timeout=5).text.strip()
        except:
            return requests.get("http://api.ipify.org", timeout=5).text.strip()

# ================= 测试调用示例 =================
if __name__ == "__main__":
    # 替换为你自己的 UID 和 UKEY
    UID = "12345" 
    UKEY = "YOUR_UKEY_HERE"
    
    xq = XieQuManager(UID, UKEY)
    
    # 1. 获取公网IP并加入白名单
    my_ip = xq.get_current_public_ip()
    xq.set_whitelist(my_ip)
    
    # 2. 获取代理 IP
    proxies = xq.get_proxy(count=1)
    if proxies:
        print(f"当前可用代理: {proxies[0]}")
    
    # 3. 任务结束后删除白名单（可选）
    # xq.del_whitelist(my_ip)
