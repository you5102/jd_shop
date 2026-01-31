import json
import asyncio
import time
import os
import httpx
import urllib.parse
import sys

# 强制刷新输出
def log(message):
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{current_time}] {message}", flush=True)

async def get_ua():
    return "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"

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
            url = f"https://api.m.jd.com/client.action?functionId=whx_getMShopOutlineInfo&body={body_enc}&t={int(time.time()*1000)}&appid=shop_view"

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
            log(f"⚠️ Vender {v_id} 请求异常: {e}")
        await asyncio.sleep(waitsecond)
    return None

async def run_task():
    start_time = time.time()
    max_runtime = 26 * 60  # 预留时间给大文件写入
    file_path = 'shop_info.json'
    
    if not os.path.exists(file_path):
        log("❌ 错误: shop_info.json 不存在")
        return

    log("📂 正在加载 JSON 文件...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f) # 正常读取
    except Exception as e:
        log(f"⚠️ 尝试严格模式读取失败，改用容错模式...")
        with open(file_path, 'r', encoding='utf-8') as f:
            content = "".join(c for c in f.read() if ord(c) >= 32 or c in "\n\r\t")
            data = json.loads(content, strict=False)

    v_keys = list(data.keys())
    total = len(v_keys)
    log(f"✅ 加载成功，共 {total} 条数据")

    processed_count = 0
    consecutive_failures = 0
    skip_count = 0 

    for v_key in v_keys:
        # 1. 时间检查
        if (time.time() - start_time) > max_runtime:
            log("🕒 时间接近上限，准备保存进度...")
            break

        # 2. 核心修正：从 data 字典中获取真正的 item 字典
        item = data.get(v_key)
        
        # 确保 item 是字典格式
        if not isinstance(item, dict):
            # 如果数据格式不对（比如是个字符串），强制转为标准格式
            data[v_key] = {"shopId": "", "shopName": "NoName"}
            item = data[v_key]

        # 3. 结构清洗：删除 item 内部的 vender 键
        if "vender" in item:
            del item["vender"]

        # 4. 检查是否需要更新
        s_id = item.get("shopId", "")
        s_name = item.get("shopName", "")
        
        # 判断条件：ID为空 或 名字为空 或 名字是 NoName
        if not s_id or not s_name or s_name == "NoName":
            log(f"🔍 正在查询 [{v_key}]...")
            result = await getshopinfo(v_key)
            
            if result:
                data[v_key].update(result) # 真正更新字典内容
                processed_count += 1
                consecutive_failures = 0
                log(f"✨ 成功: {result['shopName']}")
            else:
                consecutive_failures += 1
                log(f"🚫 失败: {v_key} (连续失败: {consecutive_failures})")

            if consecutive_failures >= 10:
                log("❌ 触发熔断：连续 10 次请求无结果，可能被封IP。")
                break
            
            await asyncio.sleep(1.2) # 频率限制
        else:
            skip_count += 1
            # 每 5000 条打印一次跳过进度
            if skip_count % 5000 == 0:  
                log(f"ℹ️ 已跳过 {skip_count} 条已存在的数据...")

    # 5. 保存数据
    log(f"💾 正在保存更新后的数据到 {file_path}...")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    log(f"🎉 处理完成！本次更新: {processed_count} 条，总数据量: {total}")

if __name__ == "__main__":
    asyncio.run(run_task())
