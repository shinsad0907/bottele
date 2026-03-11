"""
queue_manager.py
────────────────
Quản lý hàng chờ cho người dùng FREE:

• Hàng chờ ẢO  (virtual_queue): hiển thị số người chờ + thời gian (~20s/người)
  → người dùng thấy "bạn đang ở vị trí X, chờ ~Ys"

• Hàng chờ THẬT (real_queue / clothesAI): tối đa MAX_SLOTS người xử lý đồng thời
  → khi 1 người xong, người tiếp theo trong hàng được lên slot

Người dùng VIP (package != 'free') BỎ QUA hàng chờ.
"""

import asyncio
import logging
import time
from collections import deque
from script.database import (
    get_active_slots, add_to_clothesAI, remove_from_clothesAI,
    count_active_slots, set_status, set_waiting_number, get_user_db,
    MAX_SLOTS,
)

log = logging.getLogger(__name__)

VIRTUAL_WAIT_PER_PERSON = 20   # giây chờ ảo mỗi người phía trước

# ── In-memory real queue ──────────────────────────────────────────────────────
# Mỗi entry: {"user_id": str, "future": asyncio.Future, "enqueue_time": float}
_real_queue: deque = deque()
_queue_lock = asyncio.Lock()

# ── Virtual queue counter ─────────────────────────────────────────────────────
# Giả lập số người chờ ảo để hiển thị cho user
_virtual_extras: int = 2   # Mặc định luôn có ≥2 người chờ ảo khi queue trống

def _virtual_position(real_pos: int) -> tuple[int, int]:
    """
    Trả về (hiển thị_vị_trí, hiển_thị_thời_gian_giây).
    real_pos = 0 nghĩa là đang được xử lý.
    """
    display_pos  = real_pos + _virtual_extras
    display_wait = display_pos * VIRTUAL_WAIT_PER_PERSON
    return display_pos, display_wait

# ── Public API ────────────────────────────────────────────────────────────────

async def enqueue(user_id: str, progress_cb=None) -> None:
    """
    Đưa user vào hàng chờ THẬT và đợi đến lượt.
    
    progress_cb(position, wait_seconds): callback để bot gửi cập nhật hàng chờ cho user.
    Gọi hàm này với await, nó sẽ resolve khi user được lên slot xử lý.
    """
    loop = asyncio.get_event_loop()
    fut  = loop.create_future()

    async with _queue_lock:
        _real_queue.append({
            "user_id"     : str(user_id),
            "future"      : fut,
            "enqueue_time": time.time(),
        })
        pos = len(_real_queue)   # 1-indexed

    # Cập nhật DB: status = waiting, waiting = vị trí ảo
    display_pos, display_wait = _virtual_position(pos)
    set_status(str(user_id), "waiting")
    set_waiting_number(str(user_id), display_pos)

    if progress_cb:
        try:
            await progress_cb(display_pos, display_wait)
        except Exception:
            pass

    # Trigger dispatcher (nếu có slot trống)
    asyncio.ensure_future(_dispatch())

    # Chờ đến khi dispatcher giải phóng future này
    await fut


async def release(user_id: str) -> None:
    """Gọi sau khi user xử lý xong để giải phóng slot."""
    remove_from_clothesAI(str(user_id))
    set_status(str(user_id), "idle")
    set_waiting_number(str(user_id), 0)
    asyncio.ensure_future(_dispatch())


async def _dispatch() -> None:
    """
    Kiểm tra clothesAI có slot trống không.
    Nếu có → lấy người đầu queue lên, resolve future của họ.
    """
    async with _queue_lock:
        active = count_active_slots()
        while _real_queue and active < MAX_SLOTS:
            entry = _real_queue.popleft()
            uid   = entry["user_id"]
            fut   = entry["future"]

            # Thêm vào clothesAI
            ok = add_to_clothesAI(uid)
            if ok:
                set_status(uid, "processing")
                set_waiting_number(uid, 0)
                if not fut.done():
                    fut.set_result(True)
                active += 1
            else:
                # Slot đầy bất ngờ → đưa lại đầu queue
                _real_queue.appendleft(entry)
                break

        # Cập nhật số thứ tự ảo cho những người còn trong queue
        for idx, entry in enumerate(_real_queue):
            uid = entry["user_id"]
            display_pos, _ = _virtual_position(idx + 1)
            set_waiting_number(uid, display_pos)


def queue_length() -> int:
    return len(_real_queue)


def is_free_user(user_id: str) -> bool:
    u = get_user_db(str(user_id))
    if not u:
        return True
    return (u.get("package") or "free") == "free"