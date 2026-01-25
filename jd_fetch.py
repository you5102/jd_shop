import requests
import json
import time
import re
import os
import random
from fake_useragent import UserAgent

def run_task():
    url = "https://api.m.jd.com/client.action"
    vid_file = "vid.json"
    
    # 初始化随机 UA 生成器
    try:
        ua = UserAgent()
    except Exception:
        ua = None # 防御性处理

    # 1. 读取 vid.json
    if not os.path.exists(vid_file):
        print(f"❌ 错误: 找不到 {vid_file}")
        return

    with open(vid_file, "r") as f:
        try:
            vender_ids = json.load(f)
        except Exception as e:
            print(f"❌ JSON 解析失败: {e}")
            return

    error_count = 0  # 连续错误计数
    target_pattern = "2PAAf74aG3D61qvfKUM5dxUssJQ9"

    for vid in vender_ids:
        if error_count >= 5:
            print("🛑 连续报错达 5 次，程序已熔断中断。")
            break

        current_t = str(int(time.time() * 1000))
        
        # 使用 fake_useragent 生成随机 UA
        random_ua = ua.random if ua else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
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
            "uuid": "17534989146701963616779",
            "x-api-eid-token": "jdd03K6QR2YT3GL7KPXOLIFG637VJG2VAQ63BLVYVW4IF3LG7CTBI7T2EUN42IUOJQMG4TOVKQXXZMB43ZQ7CNUOAOWFARYAAAAM36NROQYYAAAAACED3TOGFVFNEJMX"
        }

        print(f"🔄 [{vid}] 正在请求... UA: {random_ua[:50]}...")

        try:
            response = requests.post(url, headers=headers, data=data, timeout=10)
            
            # 判定 HTTP 状态码
            if response.status_code != 200:
                error_count += 1
                print(f"⚠️ HTTP 错误 {response.status_code}，连续报错: {error_count}")
                continue

            res_json = response.json()
            
            # 判定业务逻辑 Code
            if res_json.get("code") != "0":
                error_count += 1
                print(f"⚠️ 业务报错: {res_json.get('msg', '未知')}，连续报错: {error_count}")
                continue

            # --- 只要业务成功，立即重置连续错误计数 ---
            error_count = 0
            
            isv_url = res_json.get("result", {}).get("signStatus", {}).get("isvUrl", "")
            if target_pattern in isv_url:
                token_match = re.search(r'token=([^&]+)', isv_url)
                token = token_match.group(1) if token_match else "None"
                print(f"✅ 匹配成功!\n🔗 URL: {isv_url}\n🔑 Token: {token}")
            else:
                print(f"ℹ️ {vid} 未匹配到目标活动")

            # 随机冷却，保护账号
            time.sleep(random.uniform(1.5, 3.5))

        except Exception as e:
            error_count += 1
            print(f"❌ 网络/解析异常: {e}，连续报错: {error_count}")

if __name__ == "__main__":
    run_task()
