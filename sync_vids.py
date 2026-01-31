import json
import asyncio
import time
import os
import httpx
import urllib.parse

# 配置参数
OLD_FILE = 'old_vid.json'
NEW_FILE = 'new_vid.json'
MAX_RUNTIME_MINS = 5      # 最大运行分钟数
MAX_QUERY_COUNT = 5000     # 单词运行最大查询 vid 数量
MAX_403_ERRORS = 10         # 允许的最大 403 报错次数

def log(message):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)

async def get_ua():
    return "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"

async def check_shop_active(v_id):
    """查询店铺信息，返回是否有效（未退店）"""
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

        async with httpx.AsyncClient(timeout=10, verify=False) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 403:
                return "403"
            
            if response.status_code == 200:
                res_json = response.json()
                shop_info = res_json.get("data", {}).get("shopInfo", {})
                shop_name = shop_info.get("shopName", "")
                
                if not shop_name:
                    return False
                if "已退店" in shop_name:
                    log(f"🚮 VID {v_id} 已退店 ({shop_name})")
                    return False
                
                log(f"✅ VID {v_id} 有效: {shop_name}")
                return True
    except Exception as e:
        log(f"⚠️ 查询 VID {v_id} 发生异常: {e}")
    return False

async def main():
    start_time = time.time()
    
    # 1. 加载文件
    if not os.path.exists(OLD_FILE) or not os.path.exists(NEW_FILE):
        log("❌ 错误: 找不到输入文件")
        return

    with open(OLD_FILE, 'r', encoding='utf-8') as f:
        old_vids = json.load(f)
    with open(NEW_FILE, 'r', encoding='utf-8') as f:
        new_vids = json.load(f)

    log(f"📊 加载完成。旧库: {len(old_vids)} 条, 当前新库: {len(new_vids)} 条")

    # 2. 定位断点
    last_vid = new_vids[-1] if new_vids else None
    start_index = 0
    
    if last_vid in old_vids:
        start_index = old_vids.index(last_vid) + 1
        log(f"📍 找到同步断点: {last_vid}，从索引 {start_index} 开始遍历")
    else:
        log("📍 未在新库中找到旧库的匹配项，将从头开始遍历旧库")

    # 3. 遍历旧库进行同步
    query_count = 0
    error_403_count = 0
    added_count = 0

    for i in range(start_index, len(old_vids)):
        current_vid = old_vids[i]
        
        # --- 熔断检查 ---
        # A. 时间检查
        if (time.time() - start_time) > (MAX_RUNTIME_MINS * 60):
            log(f"🕒 达到设定的运行时间上限 ({MAX_RUNTIME_MINS} min)，保存退出...")
            break
        
        # B. 数量检查
        if query_count >= MAX_QUERY_COUNT:
            log(f"🔢 达到单次最大查询数量 ({MAX_QUERY_COUNT})，保存退出...")
            break
            
        # C. 403 检查
        if error_403_count >= MAX_403_ERRORS:
            log(f"🚫 连续 403 报错次数达到上限 ({MAX_403_ERRORS})，疑似被封，保存退出...")
            break

        # 执行查询
        status = await check_shop_active(current_vid)
        query_count += 1

        if status == "403":
            error_403_count += 1
            log(f"🚫 收到 403 拒绝 (第 {error_403_count} 次)")
        elif status is True:
            # 只有有效且不重复才存入
            if current_vid not in new_vids:
                new_vids.append(current_vid)
                added_count += 1
            error_403_count = 0  # 成功后重置 403 计数
        
        # 控制频率
        await asyncio.sleep(1.5)

    # 4. 保存文件
    with open(NEW_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_vids, f, ensure_ascii=False, indent=2)
    
    log(f"💾 同步结束。新增: {added_count} 条，目前新库总量: {len(new_vids)}")

if __name__ == "__main__":
    asyncio.run(main())
