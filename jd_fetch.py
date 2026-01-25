import requests
import json
import time
import re

def run_task():
    url = "https://api.m.jd.com/client.action"
    current_t = str(int(time.time() * 1000))
    
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/x-www-form-urlencoded",
        "referer": "https://shop.m.jd.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "x-rp-client": "h5_1.0.0"
    }

    data = {
        "functionId": "whx_getShopHomeActivityInfo",
        "body": json.dumps({"venderId": "1000000981", "source": "m-shop"}),
        "t": current_t,
        "appid": "shop_m_jd_com",
        "clientVersion": "11.0.0",
        "client": "wh5",
        "area": "1_72_2799_0",
        "uuid": "17534989146701963616779",
        "x-api-eid-token": "jdd03K6QR2YT3GL7KPXOLIFG637VJG2VAQ63BLVYVW4IF3LG7CTBI7T2EUN42IUOJQMG4TOVKQXXZMB43ZQ7CNUOAOWFARYAAAAM36NROQYYAAAAACED3TOGFVFNEJMX"
    }

    try:
        response = requests.post(url, headers=headers, data=data, timeout=15)
        response.raise_for_status()
        res_json = response.json()

        # --- 核心逻辑：提取链接和 Token ---
        # 路径定位到 result -> signStatus -> isvUrl
        isv_url = res_json.get("result", {}).get("signStatus", {}).get("isvUrl", "")
        
        target_str = "2PAAf74aG3D61qvfKUM5dxUssJQ9"
        
        if target_str in isv_url:
            print(f"✅ 发现目标链接: {isv_url}")
            
            # 使用正则提取 token= 后的内容
            token_match = re.search(r'token=([^&]+)', isv_url)
            if token_match:
                token_value = token_match.group(1)
                print(f"🔑 提取到 Token: {token_value}")
                
                # 这里可以根据需要将 token 写入文件或发送通知
                with open("token_result.txt", "w") as f:
                    f.write(f"URL: {isv_url}\nTOKEN: {token_value}")
            else:
                print("⚠️ 链接中未找到 token 参数")
        else:
            print(f"ℹ️ 未发现包含 {target_str} 的链接")

    except Exception as e:
        print(f"❌ 发生错误: {e}")
        exit(1)

if __name__ == "__main__":
    run_task()
