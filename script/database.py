"""
database.py — Supabase REST API via httpx (no supabase-py)
"""
import httpx
import logging
from datetime import datetime

log = logging.getLogger(__name__)

SUPABASE_URL = "https://ljywfdvcwyhixuwffecp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxqeXdmZHZjd3loaXh1d2ZmZWNwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMwNDQ4MzgsImV4cCI6MjA4ODYyMDgzOH0.15mtEfJAMZPY8LT9od92g73YuJNCFPhUYzoDri0HK-s"

INIT_COINS = 100
MAX_SLOTS  = 5

HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}

def _url(table: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{table}"

# ── LOW-LEVEL ──────────────────────────────────

def _select(table: str, filters: dict) -> list:
    params = {k: f"eq.{v}" for k, v in filters.items()}
    try:
        r = httpx.get(_url(table), headers=HEADERS, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.error(f"_select {table} error: {e}")
        return []

def _insert(table: str, data: dict) -> dict | None:
    try:
        r = httpx.post(_url(table), headers=HEADERS, json=data, timeout=10)
        if not r.is_success:
            # Log chi tiết lỗi để debug
            log.error(f"_insert {table} HTTP {r.status_code}: {r.text}")
            return None
        rows = r.json()
        return rows[0] if rows else data
    except Exception as e:
        log.error(f"_insert {table} error: {e}")
        return None

def _update(table: str, filters: dict, data: dict) -> bool:
    params = {k: f"eq.{v}" for k, v in filters.items()}
    try:
        r = httpx.patch(_url(table), headers=HEADERS, params=params, json=data, timeout=10)
        if not r.is_success:
            log.error(f"_update {table} HTTP {r.status_code}: {r.text}")
            return False
        return True
    except Exception as e:
        log.error(f"_update {table} error: {e}")
        return False

# ── MANAGER USER ────────────────────────────────

def get_user(user_id: str) -> dict | None:
    rows = _select("manager_user", {"name_user": str(user_id)})
    return rows[0] if rows else None

def get_or_create_user(user_id: str, username: str = "") -> dict:
    u = get_user(str(user_id))
    if u:
        return u
    # KHÔNG có id — Supabase tự tạo uuid
    # KHÔNG insert purchase_date — để Supabase để null mặc định
    # Chỉ INSERT đúng cột có trong bảng: name_user, coin, number_create_image,
    # number_create_video, proxy, waiting, package  (không có username/status/purchase_date)
    data = {
        "name_user":           str(user_id),
        "coin":                INIT_COINS,
        "number_create_image": 0,
        "number_create_video": 0,
        "proxy":               0,
        "waiting":             0,
        "package":             "free",
    }
    result = _insert("manager_user", data)
    log.info(f"[DB] Created user {user_id} → {result}")
    return result or data

def update_user_field(user_id: str, fields: dict):
    _update("manager_user", {"name_user": str(user_id)}, fields)

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

# ── PACKAGE / PAYMENT ────────────────────────────

def set_package(user_id: str, username: str, package: str):
    """Cập nhật package trong manager_user và ghi vào bảng package."""
    update_user_field(str(user_id), {"package": package})
    _insert("package", {
        "username":      username,
        "package":       package,
        "purchase_date": datetime.now().isoformat(),
    })

def record_payment(user_id: str, username: str, pkg_id: str, amount_vnd: int):
    """
    Bảng payment: id, username, pay_package, pay_coin
    Bảng package: id, username, package, purchase_date
    """
    # Xác định là mua xu hay mua package
    is_coin = pkg_id.startswith("coin")

    # Ghi vào bảng payment
    _insert("payment", {
        "username":    username,
        "pay_package": "" if is_coin else pkg_id,
        "pay_coin":    amount_vnd if is_coin else 0,
    })

    # Nếu mua package → ghi thêm vào bảng package
    if not is_coin:
        _insert("package", {
            "username":      username,
            "package":       pkg_id,
            "purchase_date": datetime.now().isoformat(),
        })

# ── CLOTHESAI QUEUE ──────────────────────────────

def get_active_slots() -> int:
    try:
        r = httpx.get(_url("clothesAI"), headers=HEADERS, timeout=10)
        rows = r.json()
        return len([x for x in rows if x.get("status") not in ("{}", "", None)])
    except Exception as e:
        log.error(f"get_active_slots error: {e}")
        return 0

def claim_slot(user_id: str) -> bool:
    try:
        r = httpx.get(_url("clothesAI"), headers=HEADERS, timeout=10,
                      params={"status": "eq.{}", "limit": "1"})
        rows = r.json()
        if not rows:
            return False
        row_id = rows[0]["id"]
        _update("clothesAI", {"id": row_id}, {"status": str(user_id)})
        return True
    except Exception as e:
        log.error(f"claim_slot error: {e}")
        return False

def release_slot(user_id: str):
    try:
        _update("clothesAI", {"status": str(user_id)}, {"status": "{}"})
        update_user_field(str(user_id), {"waiting": 0})
    except Exception as e:
        log.error(f"release_slot error: {e}")