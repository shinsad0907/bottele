import supabase
import logging
from datetime import datetime

log = logging.getLogger(__name__)

SUPABASE_URL = "https://ljywfdvcwyhixuwffecp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxqeXdmZHZjd3loaXh1d2ZmZWNwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMwNDQ4MzgsImV4cCI6MjA4ODYyMDgzOH0.15mtEfJAMZPY8LT9od92g73YuJNCFPhUYzoDri0HK-s"

INIT_COINS    = 100
MAX_SLOTS     = 5   # Số slot tạo ảnh đồng thời tối đa (clothesAI)

def _client():
    return supabase.create_client(SUPABASE_URL, SUPABASE_KEY)

# ══════════════════════════════════════════════
#  MANAGER USER
# ══════════════════════════════════════════════

def get_user_db(user_id: str) -> dict | None:
    try:
        res = _client().from_("manager_user").select("*").eq("name_user", str(user_id)).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        log.error(f"get_user_db: {e}")
        return None

def create_user_db(user_id: str, username: str = "") -> dict:
    try:
        data = {
            "name_user"           : str(user_id),
            "username"            : username or str(user_id),
            "coin"                : INIT_COINS,
            "number_create_image" : 0,
            "number_create_video" : 0,
            "proxy"               : 0,
            "waiting"             : 0,
            "package"             : "free",
            "status"              : "idle",
            "purchase_date"       : None,
        }
        res = _client().from_("manager_user").insert(data).execute()
        log.info(f"[DB] Created user {user_id}")
        return res.data[0] if res.data else data
    except Exception as e:
        log.error(f"create_user_db: {e}")
        return {}

def get_or_create_user(user_id: str, username: str = "") -> dict:
    u = get_user_db(str(user_id))
    if not u:
        u = create_user_db(str(user_id), username)
    return u

def update_coins(user_id: str, new_coin: int):
    try:
        _client().from_("manager_user").update({"coin": new_coin}).eq("name_user", str(user_id)).execute()
    except Exception as e:
        log.error(f"update_coins: {e}")

def add_coins(user_id: str, amount: int) -> int:
    u = get_user_db(str(user_id))
    if not u:
        return 0
    new_coin = (u.get("coin") or 0) + amount
    update_coins(str(user_id), new_coin)
    return new_coin

def spend_coins(user_id: str, amount: int):
    """Trừ xu. Trả về (True, new_balance) hoặc (False, current_balance)."""
    u = get_user_db(str(user_id))
    if not u:
        return False, 0
    current = u.get("coin") or 0
    if current < amount:
        return False, current
    new_coin = current - amount
    update_coins(str(user_id), new_coin)
    return True, new_coin

def increment_image_count(user_id: str):
    u = get_user_db(str(user_id))
    if not u:
        return
    n = (u.get("number_create_image") or 0) + 1
    _client().from_("manager_user").update({"number_create_image": n}).eq("name_user", str(user_id)).execute()

def increment_video_count(user_id: str):
    u = get_user_db(str(user_id))
    if not u:
        return
    n = (u.get("number_create_video") or 0) + 1
    _client().from_("manager_user").update({"number_create_video": n}).eq("name_user", str(user_id)).execute()

def increment_proxy_count(user_id: str):
    u = get_user_db(str(user_id))
    if not u:
        return
    n = (u.get("proxy") or 0) + 1
    _client().from_("manager_user").update({"proxy": n}).eq("name_user", str(user_id)).execute()

def update_package(user_id: str, package: str, purchase_date: str = None):
    try:
        data = {
            "package"      : package,
            "purchase_date": purchase_date or datetime.now().isoformat(),
        }
        _client().from_("manager_user").update(data).eq("name_user", str(user_id)).execute()
    except Exception as e:
        log.error(f"update_package: {e}")

def set_status(user_id: str, status: str):
    """status: idle | processing | waiting"""
    try:
        _client().from_("manager_user").update({"status": status}).eq("name_user", str(user_id)).execute()
    except Exception as e:
        log.error(f"set_status: {e}")

def set_waiting_number(user_id: str, number: int):
    try:
        _client().from_("manager_user").update({"waiting": number}).eq("name_user", str(user_id)).execute()
    except Exception as e:
        log.error(f"set_waiting_number: {e}")

# ══════════════════════════════════════════════
#  CLOTHES AI — SLOT MANAGER
# ══════════════════════════════════════════════

def get_active_slots() -> list:
    """Lấy danh sách user đang processing trong clothesAI."""
    try:
        res = _client().from_("clothesAI").select("*").execute()
        return res.data or []
    except Exception as e:
        log.error(f"get_active_slots: {e}")
        return []

def count_active_slots() -> int:
    return len(get_active_slots())

def add_to_clothesAI(user_id: str) -> bool:
    """Thêm user vào clothesAI (đang xử lý). Trả về True nếu thành công."""
    try:
        active = get_active_slots()
        if len(active) >= MAX_SLOTS:
            return False
        # Kiểm tra đã có chưa
        ids = [str(r.get("user_id") or r.get("name_user", "")) for r in active]
        if str(user_id) in ids:
            return True
        _client().from_("clothesAI").insert({"user_id": str(user_id), "status": "processing"}).execute()
        return True
    except Exception as e:
        log.error(f"add_to_clothesAI: {e}")
        return False

def remove_from_clothesAI(user_id: str):
    """Xoá user khỏi clothesAI khi xong việc."""
    try:
        _client().from_("clothesAI").delete().eq("user_id", str(user_id)).execute()
    except Exception as e:
        log.error(f"remove_from_clothesAI: {e}")

# ══════════════════════════════════════════════
#  PAYMENT
# ══════════════════════════════════════════════

def insert_payment(user_id: str, username: str, payment_type: str, package_or_amount: str, price: int):
    """
    payment_type: 'coin' | 'package'
    package_or_amount: tên gói hoặc số xu
    """
    try:
        data = {
            "name_user"   : str(user_id),
            "username"    : username,
            "type"        : payment_type,
            "package"     : package_or_amount,
            "price"       : price,
            "status"      : "pending",
            "created_at"  : datetime.now().isoformat(),
        }
        _client().from_("payment").insert(data).execute()
    except Exception as e:
        log.error(f"insert_payment: {e}")

def confirm_payment(user_id: str, payment_type: str):
    """Admin xác nhận thanh toán."""
    try:
        _client().from_("payment").update({"status": "confirmed"}).eq("name_user", str(user_id)).eq("type", payment_type).eq("status", "pending").execute()
    except Exception as e:
        log.error(f"confirm_payment: {e}")