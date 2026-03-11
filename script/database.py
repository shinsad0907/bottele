"""
database.py — Supabase REST API via httpx (no supabase-py)

Cột manager_user:
  id_user, username, coin, number_create_image, number_create_video,
  proxy, waiting, package, roll_call
"""
import httpx
import logging
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)

SUPABASE_URL = "https://ljywfdvcwyhixuwffecp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxqeXdmZHZjd3loaXh1d2ZmZWNwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMwNDQ4MzgsImV4cCI6MjA4ODYyMDgzOH0.15mtEfJAMZPY8LT9od92g73YuJNCFPhUYzoDri0HK-s"

INIT_COINS        = 100
ROLLCALL_REWARD   = 100   # xu điểm danh mỗi ngày
VN_TZ             = timezone(timedelta(hours=7))

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
    rows = _select("manager_user", {"id_user": str(user_id)})
    return rows[0] if rows else None

def get_or_create_user(user_id: str, username: str = "") -> dict:
    u = get_user(str(user_id))
    if u:
        # Cập nhật username nếu thay đổi
        stored_uname = u.get("username", "")
        clean_uname = username.lstrip("@") if username else ""
        if clean_uname and stored_uname != clean_uname:
            _update("manager_user", {"id_user": str(user_id)}, {"username": clean_uname})
            u["username"] = clean_uname
        return u

    clean_uname = username.lstrip("@") if username else ""
    data = {
        "id_user":             str(user_id),
        "username":            clean_uname,
        "coin":                INIT_COINS,
        "number_create_image": 0,
        "number_create_video": 0,
        "proxy":               0,
        "waiting":             0,
        "package":             "free",
        "roll_call":           False,
    }
    result = _insert("manager_user", data)
    log.info(f"[DB] Created user {user_id} (@{clean_uname}) → {result}")
    return result or data

def update_user_field(user_id: str, fields: dict):
    _update("manager_user", {"id_user": str(user_id)}, fields)

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

# ── ROLL CALL (ĐIỂM DANH) ───────────────────────

def vn_today_str() -> str:
    """Trả về chuỗi ngày hôm nay theo giờ VN, dạng 'YYYY-MM-DD'."""
    return datetime.now(VN_TZ).strftime("%Y-%m-%d")

def do_rollcall(user_id: str) -> tuple[bool, int]:
    """
    Thực hiện điểm danh.
    Trả về (True, new_coin) nếu thành công,
            (False, cur_coin) nếu đã điểm danh hôm nay rồi.

    Logic: cột roll_call (bool) – True = đã điểm danh hôm nay.
    Hàng ngày phải reset roll_call = False từ bên ngoài hoặc
    ta kiểm tra thêm cột roll_call_date (string 'YYYY-MM-DD').
    
    Vì Supabase chỉ có cột roll_call (bool), ta dùng thêm
    cột roll_call_date để biết ngày nào đã điểm danh.
    Nếu DB chưa có cột đó thì fallback về bool đơn thuần.
    """
    u = get_user(str(user_id))
    if not u:
        return False, 0

    today = vn_today_str()
    last_date = u.get("roll_call_date", "")   # cột tuỳ chọn
    already   = u.get("roll_call", False)

    # Nếu có cột roll_call_date → dùng ngày để kiểm tra
    if last_date:
        if last_date == today:
            return False, u.get("coin", 0)
        # Ngày mới → cho điểm danh
        new_coin = (u.get("coin") or 0) + ROLLCALL_REWARD
        update_user_field(str(user_id), {
            "coin":           new_coin,
            "roll_call":      True,
            "roll_call_date": today,
        })
        return True, new_coin

    # Fallback: chỉ có cột bool roll_call
    if already:
        return False, u.get("coin", 0)

    new_coin = (u.get("coin") or 0) + ROLLCALL_REWARD
    update_user_field(str(user_id), {
        "coin":      new_coin,
        "roll_call": True,
    })
    return True, new_coin

def reset_all_rollcall():
    """Admin gọi mỗi 0h VN để reset roll_call = False cho tất cả user."""
    try:
        r = httpx.patch(
            _url("manager_user"),
            headers={**HEADERS, "Prefer": "return=minimal"},
            params={"roll_call": "eq.true"},
            json={"roll_call": False},
            timeout=15
        )
        return r.is_success
    except Exception as e:
        log.error(f"reset_all_rollcall error: {e}")
        return False

# ── PACKAGE / PAYMENT ────────────────────────────

def set_package(user_id: str, username: str, package: str):
    """Cập nhật package trong manager_user và ghi vào bảng package."""
    update_user_field(str(user_id), {"package": package})
    clean_uname = username.lstrip("@") if username else username
    _insert("package", {
        "username":      clean_uname,
        "package":       package,
        "purchase_date": datetime.now(VN_TZ).isoformat(),
    })

def record_payment(user_id: str, username: str, pkg_id: str, amount_vnd: int):
    """
    Bảng payment : id, username, pay_package, pay_coin
    Bảng package : id, username, package, purchase_date
    """
    is_coin     = pkg_id.startswith("coin")
    clean_uname = username.lstrip("@") if username else username

    _insert("payment", {
        "username":    clean_uname,
        "pay_package": "" if is_coin else pkg_id,
        "pay_coin":    amount_vnd if is_coin else 0,
    })

    if not is_coin:
        _insert("package", {
            "username":      clean_uname,
            "package":       pkg_id,
            "purchase_date": datetime.now(VN_TZ).isoformat(),
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

# ── ADMIN HELPERS ────────────────────────────────

def admin_add_coins(target_username: str, amount: int) -> tuple[bool, int]:
    """Thêm xu cho user theo username (không có @)."""
    clean = target_username.lstrip("@")
    rows = _select("manager_user", {"username": clean})
    if not rows:
        return False, 0
    u        = rows[0]
    user_id  = u["id_user"]
    new_coin = (u.get("coin") or 0) + amount
    _update("manager_user", {"id_user": user_id}, {"coin": new_coin})
    return True, new_coin

def admin_set_package(target_username: str, package: str) -> bool:
    """Cập nhật gói VIP cho user theo username."""
    clean = target_username.lstrip("@")
    rows = _select("manager_user", {"username": clean})
    if not rows:
        return False
    u       = rows[0]
    user_id = u["id_user"]
    _update("manager_user", {"id_user": user_id}, {"package": package})
    _insert("package", {
        "username":      clean,
        "package":       package,
        "purchase_date": datetime.now(VN_TZ).isoformat(),
    })
    return True

def get_user_by_username(username: str) -> dict | None:
    clean = username.lstrip("@")
    rows = _select("manager_user", {"username": clean})
    return rows[0] if rows else None