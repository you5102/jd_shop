import json
import asyncio
import time
import os
import httpx
import urllib.parse
import sys

# --- 配置参数 ---
MAX_QUERIES = 100          # 每次运行最多查询的 vid 数量
MAX_RUNTIME_SEC = 1800     # 最长运行时间（秒），例如 30 分钟
MAX_403_ERRORS = 5         # 累计遇到多少次 403 错误后停止
# ----------------

def log(message):
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{current_time}] {message}", flush=True)

async def get_ua():
    return "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"

async def getshopinfo(v_id, retrytimes=1, waitsecond=2, timeout=10):
    """
    返回元组: (result_dict, status_code)
    """
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

    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                res_json = response.json()
                shop_info = res_json.get("data", {}).get("shopInfo", {})
                if shop_info and shop_info.get("shopId") and shop_info.get("shopName"):
                    return {
                        "shopId": str(shop_info.get("shopId", "")),
                        "shopName": shop_info.get("shopName", "")
                    }, 200
                return None, 200
            return None, response.status_code
    except Exception as e:
        log(f"⚠️ Vender {v_id} 请求异常: {e}")
        return None, 999 # 自定义异常码

async def run_task():
    start_time = time.time()
    file_path = 'shop_info.json'
    
    if not os.path.exists(file_path):
        log("❌ 错误: shop_info.json 不存在")
        return

    # 加载数据
    log("📂 正在加载 JSON 文件...")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = "".join(c for c in f.read() if ord(c) >= 32 or c in "\n\r\t")
            data = json.loads(content, strict=False)

    v_keys = list(data.keys())
    log(f"✅ 加载成功，共 {len(v_keys)} 条数据")

    # 计数器
    query_count = 0        # 当前已发起的查询数
    success_count = 0      # 成功获取结果数
    error_403_count = 0    # 403 错误累计数
    skip_count = 0

    for v_key in v_keys:
        # --- 停止条件判断 ---
        
        # 1. 运行时间检查
        elapsed = time.time() - start_time
        if elapsed > MAX_RUNTIME_SEC:
            log(f"🛑 达到时间上限 ({int(elapsed)}s)，停止运行。")
            break

        # 2. 查询数量检查
        if query_count >= MAX_QUERIES:
            log(f"🛑 达到单次最大查询数 ({MAX_QUERIES})，停止运行。")
            break

        # 3. 403 错误检查
        if error_403_count >= MAX_403_ERRORS:
            log(f"🛑 累计 403 错误达 {MAX_403_ERRORS} 次，疑似封禁，停止运行。")
            break

        # --- 逻辑处理 ---
        item = data.get(v_key)
        if not isinstance(item, dict):
            data[v_key] = {"shopId": "", "shopName": "NoName"}
            item = data[v_key]

        if "vender" in item: del item["vender"]

        s_id = item.get("shopId", "")
        s_name = item.get("shopName", "")
        
        if not s_id or not s_name or s_name == "NoName":
            query_count += 1
            log(f"🔍 [{query_count}/{MAX_QUERIES}] 正在查询 {v_key}...")
            
            result, status = await getshopinfo(v_key)
            
            if status == 200:
                if result:
                    data[v_key].update(result)
                    success_count += 1
                    log(f"✨ 成功: {result['shopName']}")
                else:
                    log(f"⚠️ 未找到店铺信息: {v_key}")
            elif status == 403:
                error_403_count += 1
                log(f"🚫 触发 403 Forbidden ({error_403_count}/{MAX_403_ERRORS})")
            else:
                log(f"❓ 其他错误状态码: {status}")

            await asyncio.sleep(5) # 频率限制
        else:
            skip_count += 1
            if skip_count % 5000 == 0:
                log(f"ℹ️ 已跳过 {skip_count} 条数据...")

    # 保存数据
    log(f"💾 正在保存进度...")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    log(f"🎉 运行结束。查询: {query_count}, 成功: {success_count}, 403错误: {error_403_count}, 耗时: {int(time.time()-start_time)}s")

if __name__ == "__main__":
    async def main():
        try:
            await run_task()
        except KeyboardInterrupt:
            log("手动停止，程序退出。")

    asyncio.run(main())
