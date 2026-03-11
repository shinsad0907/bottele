"""
queue_manager.py
----------------
Quản lý hàng chờ cho user FREE:
  - MAX_SLOTS = 5 slot thật (clothesAI table)
  - Hàng chờ ảo: thêm delay 20s/vị trí trước khi chiếm slot thật
  - User VIP/paid không cần qua hàng chờ
"""
import asyncio
import logging
import time

log = logging.getLogger(__name__)

MAX_SLOTS    = 5
WAIT_PER_POS = 20  # giây mỗi vị trí hàng chờ ảo

# RAM queue: list of user_id đang chờ (FIFO)
_virtual_queue: list[str] = []
_processing:    set[str]  = set()   # đang chiếm slot thật


def is_paid(package: str) -> bool:
    return package in ("vip", "vip_pro")


# ══════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════

async def enter_queue(user_id: str, package: str, status_cb) -> bool:
    """
    Đưa user vào hàng chờ / xử lý ngay.

    status_cb(msg: str, pos: int)  →  callback gửi Telegram message cho user

    Trả về True khi đã đến lượt xử lý (slot đã được giữ).
    """
    uid = str(user_id)

    # ── VIP: bỏ qua hàng chờ ──
    if is_paid(package):
        _processing.add(uid)
        return True

    # ── Hàng chờ ảo ──
    if uid not in _virtual_queue:
        _virtual_queue.append(uid)

    # Tính vị trí ảo (số người trước mình đang chờ hoặc đang xử lý)
    virtual_pos = _virtual_queue.index(uid)  # 0-based

    if virtual_pos > 0:
        # Thông báo vị trí hàng chờ ảo
        await status_cb(
            f"⏳ *Hàng chờ ảo:* Bạn đang ở vị trí `{virtual_pos + 1}`\n"
            f"Ước tính: `{virtual_pos * WAIT_PER_POS}` giây...",
            virtual_pos
        )
        # Delay theo vị trí
        await asyncio.sleep(virtual_pos * WAIT_PER_POS)

    # Rút khỏi hàng ảo
    if uid in _virtual_queue:
        _virtual_queue.remove(uid)

    # ── Hàng chờ thật: đợi slot trống ──
    waited = 0
    attempt = 0
    while True:
        active = len(_processing)
        if active < MAX_SLOTS:
            break

        # Tính vị trí thật (bao nhiêu người đang xử lý)
        attempt += 1
        wait_msg = (
            f"⌛ *Hàng chờ:* Đang có `{active}/{MAX_SLOTS}` người xử lý\n"
            f"Bạn sẽ được lên trong giây lát... \\(`{attempt * 5}s`\\)"
        )
        await status_cb(wait_msg, active)
        await asyncio.sleep(5)
        waited += 5

        if waited > 600:   # timeout 10 phút
            return False

    _processing.add(uid)
    return True


def leave_queue(user_id: str):
    """Gọi sau khi xử lý xong (hoặc lỗi) để giải phóng slot."""
    uid = str(user_id)
    _processing.discard(uid)
    if uid in _virtual_queue:
        _virtual_queue.remove(uid)


def get_queue_info() -> dict:
    return {
        "processing": list(_processing),
        "virtual_queue": list(_virtual_queue),
        "active_slots": len(_processing),
    }