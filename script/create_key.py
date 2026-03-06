import supabase
import uuid
import requests
import os

class KeyManager:
    def __init__(self):
        self.supabase_url     = os.environ.get("SUPABASE_URL", "https://fnqgsliuvsgsxexvsxkl.supabase.co")
        self.supabase_key     = os.environ.get("SUPABASE_KEY", "sb_secret_APeL51K6QuZKDDKcOAJQdQ_4HovdJCD") 
        self.tokenapivuotlink = os.environ.get("VUOTLINK_TOKEN", "7c84f034b8aca7e6023950224fa2dee5df8edfae")

        if not self.supabase_url or not self.supabase_key:
            raise ValueError("Thieu SUPABASE_URL hoac SUPABASE_KEY trong environment variables!")

        self.client = supabase.create_client(self.supabase_url, self.supabase_key)

        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://vuotlink.vip/',
        })
        try:
            self._session.get('https://vuotlink.vip/', timeout=10)
        except Exception as e:
            print(f"[vuotlink] Khong the warm-up session: {e}")

    def _shorten_url(self, long_url, alias='') -> str:
        API_KEY = self.tokenapivuotlink

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://vuotlink.vip/',
        }

        params = {
            'api': API_KEY,
            'url': long_url,
            'alias': alias
        }

        session = requests.Session()
        session.get('https://vuotlink.vip/', headers=headers)
        res = session.get('https://vuotlink.vip/api', params=params, headers=headers)

        print("Status code:", res.status_code)
        print("Response:", res.text)

        if res.status_code != 200:
            raise Exception(f"Bi chan! Status: {res.status_code}")

        if not res.text.strip():
            raise Exception("Response rong!")

        data = res.json()
        if data['status'] == 'success':
            return data['shortenedUrl']
        else:
            raise Exception(data['message'])

    def get_or_create_key(self, user: str, ip: str, full_url: str) -> dict:
        response = (
            self.client
            .table("ppapikey")
            .select("*")
            .eq("ip_user", ip)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = response.data

        if not rows:
            return self._create_new_key(user, ip, full_url, "IP chua co key, tao moi")

        existing = rows[0]
        used     = existing.get("used")

        if used is None or used is False:
            return {
                "link_key": existing["link_key"],
                "raw_key":  existing["key"],
                "created":  False,
                "message":  "IP chua dung key, tra lai link cu"
            }
        else:
            return self._create_new_key(user, ip, full_url, "IP da dung key, tao moi")

    def _create_new_key(self, user: str, ip: str, full_url: str, message: str) -> dict:
        raw_key    = str(uuid.uuid4())
        result_url = f"{full_url}/result/{raw_key}"
        shortened  = self._shorten_url(result_url)
        print(shortened)

        data = {
            "user":     user,
            "ip_user":  ip,
            "key":      raw_key,
            "link_key": shortened,
            "used":     False,
        }
        self.client.table("ppapikey").insert(data).execute()
        print(f"[KeyManager] Key moi: {raw_key}")
        print(f"[KeyManager] Link:    {shortened}")
        return {
            "link_key": shortened,
            "raw_key":  raw_key,
            "created":  True,
            "message":  message
        }

    def mark_key_used(self, raw_key: str):
        self.client.table("ppapikey").update({"used": True}).eq("key", raw_key).execute()

    def validate_key(self, raw_key: str) -> dict:
        response = (
            self.client
            .table("ppapikey")
            .select("*")
            .eq("key", raw_key)
            .limit(1)
            .execute()
        )
        rows = response.data
        if not rows:
            return {"valid": False, "already_used": False, "row": None}
        row = rows[0]
        if row.get("used"):
            return {"valid": False, "already_used": True, "row": row}
        return {"valid": True, "already_used": False, "row": row}