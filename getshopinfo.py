import json
import asyncio
import time
import os
import httpx
import urllib.parse
import sys

# 强制刷新输出，确保日志实时显示
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
    max_runtime = 28 * 60  # 28分钟触发停止
    file_path = 'shop_info.json'
    
    if not os.path.exists(file_path):
        log("❌ 错误: shop_info.json 不存在")
        return

    # 容错读取 JSON
    log("📂 正在加载 .json...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
             data = json.loads(content, strict=False)
    except Exception as e:
        log(f"❌ JSON 加载失败: {e}，尝试强制清洗解析...")
        with open(file_path, 'r', encoding='utf-8') as f:
            # 清除非法控制字符 (ASCII 0-31)
            content = "".join(c for c in f.read() if ord(c) >= 32 or c in "\n\r\t")
             = json.loads(content, strict=False)

    v_keys = list(.keys())
    log(f"✅ 加载成功，共 {len(v_keys)} 条数据")

    processed_count = 0
    consecutive_failures = 0
    skip_count = 0  # 新增：跳过计数

    for v_key in v_keys:
        # 时间检查
        if (time.time() - start_time) > max_runtime:
            log("🕒 时间接近 30 分钟上限，保存并退出...")
            break

        item = [v_key]
        
        # 结构清洗
        if "vender" in item:
            del item["vender"]

        # 检查是否需要更新
        s_id = item.get("shopId", "")
        s_name = item.get("shopName", "")
        
        if s_id == "" or not s_id or not s_name or s_name == "" or s_name == "NoName":
            log(f"🔍 正在查询 [{v_key}]...")
            result = await getshopinfo(v_key)
            
            if result:
                [v_key].update(result)
                processed_count += 1
                consecutive_failures = 0
                log(f"✨ 成功: {result['shopName']}")
            else:
                consecutive_failures += 1
                log(f"🚫 失败: {v_key} (连续失败: {consecutive_failures})")

            if consecutive_failures >= 10:
                log("❌ 触发熔断：连续 10 次无返回。")
                break
            
            await asyncio.sleep(1.2)
        else:
            # 如果不需要更新，增加跳过计数
            skip_count += 1
            if skip_count % 5000 == 0:  # 每跳过 5000 条打印一次，证明程序活着
                log(f"ℹ️ 已跳过 {skip_count} 条无需更新的数据...")

    # 保存数据
    log("💾 正在保存更新后的数据到 shop_info.json...")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    log(f"🎉 处理完成，本次共更新 {processed_count} 条数据。")

if __name__ == "__main__":
    asyncio.run(run_task())
