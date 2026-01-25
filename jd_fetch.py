import requests
import json
import time
import os

def run_task():
    url = "https://api.m.jd.com/client.action"
    
    # 动态生成当前毫秒时间戳
    current_t = str(int(time.time() * 1000))
    
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/x-www-form-urlencoded",
        "referer": "https://shop.m.jd.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "x-rp-client": "h5_1.0.0"
    }

    # 构建请求体
    data = {
        "functionId": "whx_getShopHomeActivityInfo",
        "body": json.dumps({"venderId": "1000000981", "source": "m-shop"}),
        "t": current_t,
        "appid": "shop_m_jd_com",
        "clientVersion": "11.0.0",
        "client": "wh5",
        "area": "1_72_2799_0",
        "uuid": "17534989146701963616779",
        # token 建议通过 Secrets 传入，如果固定则直接写死
        "x-api-eid-token": "jdd03K6QR2YT3GL7KPXOLIFG637VJG2VAQ63BLVYVW4IF3LG7CTBI7T2EUN42IUOJQMG4TOVKQXXZMB43ZQ7CNUOAOWFARYAAAAM36NROQYYAAAAACED3TOGFVFNEJMX"
    }

    print(f"🚀 开始请求京东 API, 时间戳: {current_t}")
    
    try:
        response = requests.post(url, headers=headers, data=data, timeout=15)
        response.raise_for_status()
        
        result = response.json()
        print("✅ 请求成功！")
        # 打印部分结果防止日志过长
        print(json.dumps(result, indent=2, ensure_ascii=False)[:500] + "...")
        
    except Exception as e:
        print(f"❌ 请求发生异常: {e}")
        exit(1) # 报错时让 GitHub Action 显示失败

if __name__ == "__main__":
    run_task()
