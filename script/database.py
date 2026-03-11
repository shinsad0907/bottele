import supabase
import logging
from datetime import datetime

log = logging.getLogger(__name__)

SUPABASE_URL = "https://ljywfdvcwyhixuwffecp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxqeXdmZHZjd3loaXh1d2ZmZWNwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMwNDQ4MzgsImV4cCI6MjA4ODYyMDgzOH0.15mtEfJAMZPY8LT9od92g73YuJNCFPhUYzoDri0HK-s"

INIT_COINS    = 100
MAX_SLOTS     = 5   # Tối đa bao nhiêu người tạo cùng lúc trong clothesAI

def _client():
    return supabase.create_client(SUPABASE_URL, SUPABASE_KEY)

# ══════════════════════════════════════════════
#  MANAGER USER
# ══════════════════════════════════════════════

def get_user(user_id: str) -> dict | None:
    try:
        res = _client().from_("manager_user").select("*").eq("name_user", str(user_id)).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        log.error(f"get_user error: {e}")
        return None

def get_or_create_user(user_id: str, username: str = "") -> dict:
    u = get_user(str(user_id))
    if u:
        return u
    try:
        data = {
            "name_user":           str(user_id),
            "username":            username or str(user_id),
            "coin":                INIT_COINS,
            "number_create_image": 0,
            "number_create_video": 0,
            "proxy":               0,
            "waiting":             0,
            "package":             "free",
            "status":              "idle",
            "purchase_date":       None,
        }
        res = _client().from_("manager_user").insert(data).execute()
        log.info(f"[DB] Created user {user_id}")
        return res.data[0] if res.data else data
    except Exception as e:
        log.error(f"create_user error: {e}")
        return {}

def update_user_field(user_id: str, fields: dict):
    try:
        _client().from_("manager_user").update(fields).eq("name_user", str(user_id)).execute()
    except Exception as e:
        log.error(f"update_user_field error: {e}")

def add_coins(user_id: str, amount: int) -> int:
    u = get_user(str(user_id))
    if not u:
        return 0
    new_coin = (u.get("coin") or 0) + amount
    update_user_field(str(user_id), {"coin": new_coin})
    return new_coin

def spend_coins(user_id: str, amount: int) -> tuple[bool, int]:
    u = get_user(str(user_id))
    if not u:
        return False, 0
    cur = u.get("coin") or 0
    if cur < amount:
        return False, cur
    new_coin = cur - amount
    update_user_field(str(user_id), {"coin": new_coin})
    return True, new_coin

def inc_image_count(user_id: str):
    u = get_user(str(user_id))
    if u:
        update_user_field(str(user_id), {
            "number_create_image": (u.get("number_create_image") or 0) + 1
        })

def inc_video_count(user_id: str):
    u = get_user(str(user_id))
    if u:
        update_user_field(str(user_id), {
            "number_create_video": (u.get("number_create_video") or 0) + 1
        })

def inc_proxy(user_id: str):
    u = get_user(str(user_id))
    if u:
        update_user_field(str(user_id), {
            "proxy": (u.get("proxy") or 0) + 1
        })

# ══════════════════════════════════════════════
#  PACKAGE / PAYMENT
# ══════════════════════════════════════════════

def set_package(user_id: str, package: str):
    update_user_field(str(user_id), {
        "package":       package,
        "purchase_date": datetime.now().isoformat(),
    })

def record_payment(user_id: str, username: str, package_or_coin: str, amount_vnd: int):
    """Ghi lịch sử thanh toán vào bảng payment."""
    try:
        _client().from_("payment").insert({
            "name_user":  str(user_id),
            "username":   username,
            "type":       package_or_coin,
            "amount_vnd": amount_vnd,
            "created_at": datetime.now().isoformat(),
        }).execute()
    except Exception as e:
        log.error(f"record_payment error: {e}")

# ══════════════════════════════════════════════
#  CLOTHESAI QUEUE (real queue table)
# ══════════════════════════════════════════════

def get_active_slots() -> int:
    """Đếm số slot đang xử lý trong clothesAI."""
    try:
        res = _client().from_("clothesAI").select("status").execute()
        active = [r for r in (res.data or []) if r.get("status") not in ("{}", "", None)]
        return len(active)
    except Exception as e:
        log.error(f"get_active_slots error: {e}")
        return 0

def claim_slot(user_id: str) -> bool:
    """Thử chiếm 1 slot trong clothesAI. Trả True nếu thành công."""
    try:
        res = _client().from_("clothesAI").select("*").in_("status", ["{}", ""]).limit(1).execute()
        if not res.data:
            return False
        row_id = res.data[0]["id"]
        _client().from_("clothesAI").update({
            "status": str(user_id)
        }).eq("id", row_id).execute()
        update_user_field(str(user_id), {"status": "processing"})
        return True
    except Exception as e:
        log.error(f"claim_slot error: {e}")
        return False

def release_slot(user_id: str):
    """Giải phóng slot sau khi xử lý xong."""
    try:
        _client().from_("clothesAI").update({"status": "{}"}).eq("status", str(user_id)).execute()
        update_user_field(str(user_id), {"status": "idle", "waiting": 0})
    except Exception as e:
        log.error(f"release_slot error: {e}")

def get_queue_position(user_id: str) -> int:
    """Trả về vị trí trong hàng chờ (0 = đang xử lý)."""
    try:
        u = get_user(str(user_id))
        return u.get("waiting", 0) if u else 0
    except:
        return 0

def set_waiting(user_id: str, pos: int):
    update_user_field(str(user_id), {"waiting": pos})