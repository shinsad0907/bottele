import requests
import supabase

class payment_clothesAI:
    def __init__(self):
        self.API_bot = "8712430335:AAGBsFNLflx7BXZpjgQ_fMesAqF76gAgUCk"
    def send_message(self, chat_id, text):
        url = f"https://api.telegram.org/bot{self.API_bot}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text
        }
        response = requests.post(url, json=payload)
        return response.json()
class ManagerUser:
    def __init__(self):
        self.API_Keys = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxqeXdmZHZjd3loaXh1d2ZmZWNwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMwNDQ4MzgsImV4cCI6MjA4ODYyMDgzOH0.15mtEfJAMZPY8LT9od92g73YuJNCFPhUYzoDri0HK-s"
        self.supabase_url = "https://ljywfdvcwyhixuwffecp.supabase.co"

    def get_user(self, username):
        client = supabase.create_client(self.supabase_url, self.API_Keys)
        response = client.from_("manager_user").select("*").execute()
        return response.data    
    def update_user(self, username, new_data):
        client = supabase.create_client(self.supabase_url, self.API_Keys)
        response = client.from_("manager_user").update(new_data).eq("username", username).execute()
        return response.data
    def update_coin_user(self, username, new_coin):
        client = supabase.create_client(self.supabase_url, self.API_Keys)
        response = client.from_("manager_user").update({"coin": new_coin}).eq("username", username).execute()
        return response.data
    def update_number_create_image(self, username, new_number):
        client = supabase.create_client(self.supabase_url, self.API_Keys)
        response = client.from_("manager_user").update({"number_create_image": new_number}).eq("username", username).execute()
        return response.data
    def update_number_create_video(self, username, new_number):
        client = supabase.create_client(self.supabase_url, self.API_Keys)
        response = client.from_("manager_user").update({"number_create_video": new_number}).eq("username", username).execute()
        return response.data
    def update_proxy(self, username, new_number):
        client = supabase.create_client(self.supabase_url, self.API_Keys)
        response = client.from_("manager_user").update({"proxy": new_number}).eq("username", username).execute()
        return response.data
    def waiting_user(self, username):
        client = supabase.create_client(self.supabase_url, self.API_Keys)
        response = client.from_("manager_user").update({"status": "waiting"}).eq("username", username).execute()
        return response.data
    def package_user(self, username, package):
        client = supabase.create_client(self.supabase_url, self.API_Keys)
        response = client.from_("manager_user").update({"package": package}).eq("username", username).execute()
        return response.data
    
class manager_clothesAI:
    def __init__(self):
        self.API_Keys = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxqeXdmZHZjd3loaXh1d2ZmZWNwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMwNDQ4MzgsImV4cCI6MjA4ODYyMDgzOH0.15mtEfJAMZPY8LT9od92g73YuJNCFPhUYzoDri0HK-s"
        self.supabase_url = "https://ljywfdvcwyhixuwffecp.supabase.co"
        self.client = supabase.create_client(self.supabase_url, self.API_Keys)
    def get_status(self):
        response = self.client.from_("clothesAI").select("*").execute()
        return response.data 
    def update_status(self):
        response = self.client.from_("clothesAI").update({"status": "{}"}).execute()
        return response.data
    
class payment:
    def __init__(self):
        self.API_Keys = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxqeXdmZHZjd3loaXh1d2ZmZWNwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMwNDQ4MzgsImV4cCI6MjA4ODYyMDgzOH0.15mtEfJAMZPY8LT9od92g73YuJNCFPhUYzoDri0HK-s"
        self.supabase_url = "https://ljywfdvcwyhixuwffecp.supabase.co"
        self.client = supabase.create_client(self.supabase_url, self.API_Keys)

    def pay_package(self, username, package):
        response = self.client.from_("payment").insert({"username": username, "package": package}).execute()
        return response.data

    def pay_coin(self, username):
        response = self.client.from_("payment").select("*").eq("username", username).execute()
        return response.data
    
class ManagerUserPackage:
    def __init__(self):
        self.API_Keys = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxqeXdmZHZjd3loaXh1d2ZmZWNwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMwNDQ4MzgsImV4cCI6MjA4ODYyMDgzOH0.15mtEfJAMZPY8LT9od92g73YuJNCFPhUYzoDri0HK-s"
        self.supabase_url = "https://ljywfdvcwyhixuwffecp.supabase.co"
        self.client = supabase.create_client(self.supabase_url, self.API_Keys)

    def update_package(self, username, new_package, purchase_date):
        response = self.client.from_("manager_user").update({"package": new_package}).eq("username", username).execute()
        response = self.client.from_("manager_user").update({"package": new_package}).eq("purchase_date", purchase_date).execute()
        return response.data

print(ManagerUser().get_user("shin"))