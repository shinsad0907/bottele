"""
database.py — Supabase REST API via httpx (no supabase-py)

Cột manager_user:
  id_user, username, coin, number_create_image, number_create_video,
  proxy, waiting, package, roll_call
"""
import httpx
import logging
from datetime import datetime, timezone, timedelta

# from templates.bottele import get_user

log = logging.getLogger(__name__)

SUPABASE_URL = "https://ljywfdvcwyhixuwffecp.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxqeXdmZHZjd3loaXh1d2ZmZWNwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMwNDQ4MzgsImV4cCI6MjA4ODYyMDgzOH0.15mtEfJAMZPY8LT9od92g73YuJNCFPhUYzoDri0HK-s"

INIT_COINS        = 100
ROLLCALL_REWARD   = 300   # xu điểm danh gói Free
VN_TZ             = timezone(timedelta(hours=7))

# Xu điểm danh theo gói
ROLLCALL_BY_PKG = {
    "free":    300,
    "vip":     1500,
    "vip_pro": 5000,
}

HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}

REFERRAL_REWARD_INVITER = 500   # người mời
REFERRAL_REWARD_INVITEE = 300   # người được mời

REFERRAL_REWARD_INVITER = 500
REFERRAL_REWARD_INVITEE = 300

def apply_referral(new_user_id: str, inviter_id: str) -> tuple[bool, int, int]:
    """
    Ghi nhận referral khi người mới /start lần đầu qua link mời.
    Trả về (success, new_coin_inviter, new_coin_invitee)
    """
    user = get_user(new_user_id)
    if not user:
        return False, 0, 0
    if user.get("referred_by"):       # đã được mời rồi
        return False, 0, 0
    if new_user_id == inviter_id:     # tự mời mình
        return False, 0, 0

    inviter = get_user(inviter_id)
    if not inviter:
        return False, 0, 0

    # Cộng xu + tăng referral_count cho người mời
    new_inviter_coin = (inviter.get("coin") or 0) + REFERRAL_REWARD_INVITER
    _update("manager_user", {"id_user": inviter_id}, {
        "coin":           new_inviter_coin,
        "referral_count": (inviter.get("referral_count") or 0) + 1,
    })

    # Cộng xu + ghi referred_by cho người được mời
    new_invitee_coin = (user.get("coin") or 0) + REFERRAL_REWARD_INVITEE
    _update("manager_user", {"id_user": new_user_id}, {
        "coin":        new_invitee_coin,
        "referred_by": inviter_id,
    })

    return True, new_inviter_coin, new_invitee_coin


def get_referral_stats(user_id: str) -> dict:
    """Trả về số người đã mời và tổng xu kiếm được từ referral."""
    user = get_user(str(user_id))
    if not user:
        return {"count": 0, "earned": 0}
    count = user.get("referral_count") or 0
    return {
        "count":  count,
        "earned": count * REFERRAL_REWARD_INVITER,
    }

MAX_EXTERNAL_PER_DAY = 2

# Tên cột thật trong bảng external_link — sẽ được tự detect khi chạy lần đầu
_IP_COL   = None   # tên cột chứa IP
_DATE_COL = None   # tên cột chứa ngày
_CNT_COL  = None   # tên cột chứa số đếm


def _detect_external_link_cols() -> tuple[str | None, str | None, str | None]:
    """
    Lấy 1 row bất kỳ từ external_link để đọc tên cột thật.
    Trả về (ip_col, date_col, count_col).
    """
    global _IP_COL, _DATE_COL, _CNT_COL
    if _IP_COL:
        return _IP_COL, _DATE_COL, _CNT_COL

    try:
        r = httpx.get(_url("external_link"), headers=HEADERS,
                      params={"limit": "1"}, timeout=10)
        if not r.is_success:
            log.error(f"[DETECT_COLS] {r.status_code}: {r.text[:200]}")
            return None, None, None

        rows = r.json()
        if not rows:
            # Bảng trống → lấy từ header PostgREST (Content-Range)
            log.warning("[DETECT_COLS] bảng external_link rỗng, không detect được cột")
            return None, None, None

        keys = list(rows[0].keys())
        log.info(f"[DETECT_COLS] tên cột thật: {keys}")

        # Tìm cột IP: chứa 'ip' không phân biệt hoa thường
        ip_col = next((k for k in keys if k.lower() == "ip"), None)
        # Tìm cột date: chứa 'date'
        date_col = next((k for k in keys
                         if "date" in k.lower() and k.lower() != "id"), None)
        # Tìm cột count: chứa 'number' hoặc 'count'
        cnt_col = next((k for k in keys
                        if "number" in k.lower() or "count" in k.lower()), None)

        log.info(f"[DETECT_COLS] ip={ip_col!r} date={date_col!r} count={cnt_col!r}")

        _IP_COL   = ip_col
        _DATE_COL = date_col
        _CNT_COL  = cnt_col
        return ip_col, date_col, cnt_col

    except Exception as e:
        log.error(f"[DETECT_COLS] exception: {e}")
        return None, None, None


def check_and_inc_ip_limit(ip: str) -> tuple[bool, int]:
    """
    Kiểm tra và tăng bộ đếm vượt link theo IP + ngày.
    Tự detect tên cột từ bảng external_link.

    Trả về:
        (True,  count)  → còn trong giới hạn
        (False, count)  → đã hết lượt hôm nay
    """
    today = vn_today_str()

    # ── Bước 1: detect tên cột ───────────────────────────────────────────────
    ip_col, date_col, cnt_col = _detect_external_link_cols()

    if not ip_col or not date_col or not cnt_col:
        log.warning("[IP_LIMIT] không detect được cột → bỏ qua giới hạn")
        return True, 0

    # ── Bước 2: lấy tất cả row của IP này ───────────────────────────────────
    try:
        r = httpx.get(
            _url("external_link"),
            headers=HEADERS,
            params={ip_col: f"eq.{ip}"},
            timeout=10,
        )
        log.info(f"[IP_LIMIT] query status={r.status_code}")

        if not r.is_success:
            log.error(f"[IP_LIMIT] lỗi query: {r.text[:200]}")
            return True, 0

        rows = r.json()

    except Exception as e:
        log.error(f"[IP_LIMIT] exception: {e}")
        return True, 0

    # ── Bước 3: tìm row hôm nay ─────────────────────────────────────────────
    today_row = None
    for row in rows:
        d = str(row.get(date_col) or "")
        if today in d:
            today_row = row
            break

    # ── Bước 4: xử lý ───────────────────────────────────────────────────────
    if today_row:
        row_id  = today_row.get("id")
        current = today_row.get(cnt_col) or 0

        if current >= MAX_EXTERNAL_PER_DAY:
            log.info(f"[IP_LIMIT] {ip} đã hết lượt ({current}/{MAX_EXTERNAL_PER_DAY})")
            return False, current

        new_count = current + 1
        try:
            httpx.patch(
                _url("external_link"),
                headers=HEADERS,
                params={"id": f"eq.{row_id}"},
                json={
                    cnt_col:  new_count,
                    date_col: today,
                },
                timeout=10,
            )
            log.info(f"[IP_LIMIT] {ip} cập nhật count={new_count}")
        except Exception as e:
            log.error(f"[IP_LIMIT] patch error: {e}")

        return True, new_count

    else:
        # Chưa có record hôm nay → INSERT mới
        insert_data = {
            ip_col:   ip,
            date_col: today,
            cnt_col:  1,
            "use":    False,
            "url_shorten_key": "__ip_track__",
        }
        try:
            ri = httpx.post(
                _url("external_link"),
                headers=HEADERS,
                json=insert_data,
                timeout=10,
            )
            log.info(f"[IP_LIMIT] INSERT status={ri.status_code} body={ri.text[:150]}")
        except Exception as e:
            log.error(f"[IP_LIMIT] insert error: {e}")

        return True, 1
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
    if not rows:
        return None
    u = rows[0]
    # Normalize package: "VIP" → "vip", "VIP_PRO"/"VIP PRE"/"VIP_PRE" → "vip_pro"
    if u.get("package"):
        pkg = u["package"].lower().strip().replace(" ", "_")
        if "pre" in pkg or "pro" in pkg:
            pkg = "vip_pro"
        elif "vip" in pkg:
            pkg = "vip"
        else:
            pkg = "free"
        u["package"] = pkg
    return u

def _normalize_user(u: dict) -> dict:
    """Normalize các field từ DB về đúng format code dùng."""
    if u and u.get("package"):
        u["package"] = u["package"].lower().replace(" ", "_").replace("pre", "pro")
    return u

def get_or_create_user(user_id: str, username: str = "") -> dict:
    u = get_user(str(user_id))
    if u:
        u = _normalize_user(u)
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

def do_rollcall(user_id: str) -> tuple[bool, int, int]:
    """
    Thực hiện điểm danh theo gói của user.
    Trả về (True, new_coin, reward) nếu thành công,
            (False, cur_coin, 0)    nếu đã điểm danh hôm nay rồi.
    Xu thưởng: Free=300 · VIP=1500 · VIP PRE=5000
    """
    u = get_user(str(user_id))
    if not u:
        return False, 0, 0

    today     = vn_today_str()
    last_date = u.get("roll_call_date", "")
    already   = u.get("roll_call", False)
    package   = u.get("package", "free")
    reward    = ROLLCALL_BY_PKG.get(package, ROLLCALL_REWARD)

    # Nếu có cột roll_call_date → dùng ngày để kiểm tra
    if last_date:
        if last_date == today:
            return False, u.get("coin", 0), 0
        # Ngày mới → cho điểm danh
        new_coin = (u.get("coin") or 0) + reward
        update_user_field(str(user_id), {
            "coin":           new_coin,
            "roll_call":      True,
            "roll_call_date": today,
        })
        return True, new_coin, reward

    # Fallback: chỉ có cột bool roll_call
    if already:
        return False, u.get("coin", 0), 0

    new_coin = (u.get("coin") or 0) + reward
    update_user_field(str(user_id), {
        "coin":      new_coin,
        "roll_call": True,
    })
    return True, new_coin, reward

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
      - Mua xu  : pay_package = None, pay_coin = amount_vnd (tiền VND)
      - Mua VIP : pay_package = pkg_id, pay_coin = 0
    Admin duyệt thủ công rồi mới /addcoins hoặc /setpackage.
    """
    is_coin     = pkg_id.startswith("coin")
    clean_uname = username.lstrip("@") if username else username

    row = {"username": clean_uname}
    if is_coin:
        row["pay_package"] = None
        row["pay_coin"]    = amount_vnd
    else:
        row["pay_package"] = pkg_id
        row["pay_coin"]    = 0

    _insert("payment", row)

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
