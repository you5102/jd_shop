import json
import os

def clean_vid_files():
    # 配置路径
    shop_info_path = 'shop_info.json'
    old_folder = 'oldvid'
    new_folder = 'newvid'

    # 1. 确保输出目录存在
    if not os.path.exists(new_folder):
        os.makedirs(new_folder)
        print(f"创建目录: {new_folder}")

    # 2. 读取 shop_info.json
    try:
        with open(shop_info_path, 'r', encoding='utf-8') as f:
            shop_data = json.load(f)
    except FileNotFoundError:
        print(f"错误：找不到 {shop_info_path}")
        return

    # 3. 定义过滤函数
    def is_valid_vid(vid):
        vid_str = str(vid)
        if vid_str in shop_data:
            shop_name = shop_data[vid_str].get('shopName', '')
            # 检查是否包含“退店”或“无效”
            if "退店" not in shop_name and "无效" not in shop_name:
                return True
        return False

    # 4. 遍历 oldvid 文件夹
    files_processed = 0
    for filename in os.listdir(old_folder):
        if filename.endswith('.json'):
            old_file_path = os.path.join(old_folder, filename)
            new_file_path = os.path.join(new_folder, filename)

            try:
                # 读取旧的 vid 列表
                with open(old_file_path, 'r', encoding='utf-8') as f:
                    vids = json.load(f)
                
                if not isinstance(vids, list):
                    print(f"跳过文件 {filename}：数据格式不是数组")
                    continue

                # 过滤无效 vid
                cleaned_vids = [vid for vid in vids if is_valid_vid(vid)]

                # 写入新文件（覆盖写入）
                with open(new_file_path, 'w', encoding='utf-8') as f:
                    json.dump(cleaned_vids, f, ensure_ascii=False, indent=4)
                
                files_processed += 1
                print(f"已处理: {filename} ({len(vids)} -> {len(cleaned_vids)})")

            except Exception as e:
                print(f"处理文件 {filename} 时出错: {e}")

    print(f"\n任务完成！共处理文件数: {files_processed}")

if __name__ == "__main__":
    clean_vid_files()
