import requests
import json
from datetime import datetime, timedelta, timezone

class DataWorkerClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": api_key
        }
        # 定义北京时区 (UTC+8)
        self.beijing_tz = timezone(timedelta(hours=8))
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _get_bj_now(self):
        """无论系统时区是什么，始终返回当前的北京时间对象"""
        return datetime.now(timezone.utc).astimezone(self.beijing_tz)

    def _format_date(self, dt_obj):
        """格式化为 MM_DD"""
        return dt_obj.strftime("%m_%d")

    def upload(self, data):
        """上传数据"""
        url = f"{self.base_url}/upload"
        try:
            response = self.session.post(url, data=json.dumps(data), timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Upload Error: {e}")
            return False

    def get_today_data(self):
        """获取北京时间的今天数据"""
        date_str = self._format_date(self._get_bj_now())
        return self._fetch(date_str)

    def get_yesterday_data(self):
        """获取北京时间的昨天数据"""
        yesterday_obj = self._get_bj_now() - timedelta(days=1)
        date_str = self._format_date(yesterday_obj)
        return self._fetch(date_str)

    def _fetch(self, date_str):
        """底层请求函数"""
        url = f"{self.base_url}/get"
        try:
            print(f"🔍 正在查询北京时间 {date_str} 的数据...")
            response = self.session.get(url, params={"date": date_str}, timeout=10)
            return response.json() if response.status_code == 200 else []
        except Exception as e:
            print(f"Get Error: {e}")
            return []

# --- 调用演示 ---
if __name__ == "__main__":
    worker = DataWorkerClient("https://token.zshyz.us.ci", "leaflow")
    
    # 获取昨天数据
    yesterday = worker.get_yesterday_data()
    print(f"昨天数据: {yesterday}")
    
    # 上传并获取今天
    worker.upload({"vid": 8999, "token": "cstoken"})
    today = worker.get_today_data()
    print(f"今天数据: {today}")
