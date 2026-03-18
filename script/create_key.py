from supabase import create_client
import uuid
import requests
import os

class KeyManager:
    def __init__(self, user_id=None, username=None, url_web="bottele-lilac.vercel.app"):
        self.user_id = user_id
        self.username = username
        self.url_web = url_web
        self.SUPABASE_URL = "https://ljywfdvcwyhixuwffecp.supabase.co"
        self.SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxqeXdmZHZjd3loaXh1d2ZmZWNwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMwNDQ4MzgsImV4cCI6MjA4ODYyMDgzOH0.15mtEfJAMZPY8LT9od92g73YuJNCFPhUYzoDri0HK-s"
        self.api_token = "69ad89d5a7b0c143fe257cde"
        self.supabase = create_client(self.SUPABASE_URL, self.SUPABASE_KEY)
        self._session = requests.Session()

    def shorten_link(self, url):
        api_url = f"https://link4m.co/api-shorten/v2?api={self.api_token}&url={url}"
        response = self._session.get(api_url)
        if response.status_code == 200:
            return response.json().get("shortenedUrl")
        else:
            raise Exception(f"Failed to shorten link: {response.status_code}")

    def create_key(self):
        id_key = str(uuid.uuid4())
        data = {
            "user": self.user_id,
            "id": id_key,
            "key": str(uuid.uuid4()),
            "username": self.username,
            "use": False,
            "url_shorten_key": self.shorten_link(f"{self.url_web}/{id_key}"),
        }
        res = self.supabase.table("external_link").insert(data).execute()
        return res.data[0]["id"]

    def get_key(self):
        res = self.supabase.table("external_link").select("*").execute()
        for item in res.data:
            if item["user"] == self.user_id and (item['use'] == False or item['use'] is None):
                return item["id"]
        return self.create_key()

    def check_key(self, key):
        # Query theo cột "key", không phải cột "id"
        res = self.supabase.table("external_link").select("*").eq("key", key).execute()
        if not res.data:
            return False

        item = res.data[0]
        if item['use'] == False or item['use'] is None:
            # Đánh dấu đã dùng
            self.supabase.table("external_link").update({"use": True}).eq("key", key).execute()
            return True

        return False