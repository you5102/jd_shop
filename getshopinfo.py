import json
import asyncio
import time
import os
import httpx
import urllib.parse

# 获取 User-Agent
async def get_ua():
    return "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"

# 店铺查询函数
async def getshopinfo(v_id, retrytimes=2, waitsecond=2, timeout=10):
    for i in range(retrytimes):
        try:
            ua = await get_ua()
            headers = {
                'accept': 'application/json, text/plain, */*',
                'Origin': 'https://shop.m.jd.com/',
                'Referer': 'https://shop.m.jd.com/',
                'User-Agent': ua
            }
            
            body = {"venderId": str(v_id), "source": "m-shop"}
            body_enc = urllib.parse.quote(json.dumps(body))
            timestamp = int(time.time() * 1000)
            url = f"https://api.m.jd.com/client.action?functionId=whx_getMShopOutlineInfo&body={body_enc}&t={timestamp}&appid=shop_view"

            async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    res_json = response.json()
                    shop_info = res_json.get("data", {}).get("shopInfo", {})
                    if shop_info and shop_info.get("shopId"):
                        return {
                            "shopId": str(shop_info.get("shopId", "")),
                            "shopName": shop_info.get("shopName", "")
                        }
        except Exception as e:
            print(f"查询 Vender {v_id} 报错: {e}")

        await asyncio.sleep(waitsecond)
    return None

async def run_task():
    start_time = time.time()  # 记录程序开始时间
    max_runtime = 28 * 60     # 设置最大运行时间为 28 分钟 (预留 2 分钟给 Git 提交)
    
    file_path = 'shop_info.json'
    if not os.path.exists(file_path):
        print("data.json 文件不存在")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    processed_count = 0
    consecutive_failures = 0
    max_failures = 10

    vender_keys = list(data.keys())
    for v_key in vender_keys:
        # --- 运行时间检查 ---
        elapsed_time = time.time() - start_time
        if elapsed_time > max_runtime:
            print(f"⏰ 已运行 {elapsed_time/60:.1f} 分钟，接近 30 分钟上限，正在保存并退出...")
            break

        item = data[v_key]
        
        # 1. 如果元素里含有 "vender" 键，就把它删掉
        if "vender" in item:
            del item["vender"]

        # 2. 判断是否需要查询
        s_id = item.get("shopId", "")
        s_name = item.get("shopName", "")

        if s_id == "" or not s_name or s_name == "NoName":
            print(f"正在更新: {v_key}...")
            result = await getshopinfo(v_key)
            
            if result:
                data[v_key]["shopId"] = result["shopId"]
                data[v_key]["shopName"] = result["shopName"]
                processed_count += 1
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                print(f"警告: {v_key} 获取失败，连续失败次数: {consecutive_failures}")

            # 3. 熔断机制：连续失败 10 次停止
            if consecutive_failures >= max_failures:
                print(f"❌ 连续失败 {max_failures} 次，停止程序。")
                break
            
            await asyncio.sleep(1.2) # 基础间隔频率控制

    # 4. 保存结果（无论是自然跑完、超时还是熔断，都保存当前进度）
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    print(f"处理结束。本次共更新了 {processed_count} 个店铺信息。")

if __name__ == "__main__":
    asyncio.run(run_task())
