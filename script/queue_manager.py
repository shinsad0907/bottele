"""
queue_manager.py
----------------
Quản lý hàng chờ cho user FREE:
  - MAX_SLOTS = 5 slot thật
  - Hàng chờ ảo: nếu queue thực = 0 → hiện "2 người đang xử lý" fake + delay 5s
  - Nếu queue thực > 0 → nối tiếp thật, không fake
  - VIP / VIP_PRO: không qua hàng chờ, xử lý ngay
"""
import asyncio
import logging

log = logging.getLogger(__name__)

MAX_SLOTS    = 5
WAIT_PER_POS = 20   # giây delay mỗi vị trí hàng chờ thật
FAKE_QUEUE   = 2    # số người ảo hiện khi queue thực = 0
FAKE_DELAY   = 5    # giây delay khi hiện hàng chờ ảo

# RAM queue
_virtual_queue: list[str] = []
_processing:    set[str]  = set()


def is_paid(package: str) -> bool:
    return package in ("vip", "vip_pro")


async def enter_queue(user_id: str, package: str, status_cb) -> bool:
    """
    VIP/VIP_PRO → xử lý ngay, không hàng chờ.
    FREE        → hàng chờ ảo (nếu queue = 0) hoặc hàng chờ thật.

    Trả về True khi đến lượt, False nếu timeout.
    """
    uid = str(user_id)

    # ── VIP / VIP_PRO: bỏ qua hoàn toàn ──
    if is_paid(package):
        _processing.add(uid)
        return True

    # ── FREE: thêm vào hàng chờ ảo ──
    if uid not in _virtual_queue:
        _virtual_queue.append(uid)

    active_real = len(_processing)

    # Trường hợp 1: Queue thực = 0 → hiện hàng chờ ảo FAKE_QUEUE người
    if active_real == 0:
        await status_cb(
            f"⏳ *Đang kiểm tra hàng chờ\\.\\.\\.*\n\n"
            f"```\n"
            f"  👥 Trước bạn:  {FAKE_QUEUE} người đang xử lý\n"
            f"  ⏱  Ước tính:  ~{FAKE_DELAY * FAKE_QUEUE}s\n"
            f"  🔄 Đang chờ slot trống\\.\\.\\.\n"
            f"```",
            FAKE_QUEUE
        )
        await asyncio.sleep(FAKE_DELAY)
        # Sau delay → vào slot ngay
        if uid in _virtual_queue:
            _virtual_queue.remove(uid)
        _processing.add(uid)
        return True

    # Trường hợp 2: Queue thực > 0 → hàng chờ thật, nối tiếp
    virtual_pos = _virtual_queue.index(uid)  # 0-based
    total_ahead = active_real + virtual_pos

    if total_ahead > 0:
        await status_cb(
            f"⏳ *ĐANG XẾP HÀNG CHỜ*\n\n"
            f"```\n"
            f"  👥 Vị trí:    #{total_ahead + 1}\n"
            f"  🔄 Đang xử lý: {active_real}/{MAX_SLOTS} người\n"
            f"  ⏱  Ước tính:  ~{total_ahead * WAIT_PER_POS}s\n"
            f"```\n\n"
            f"_Vui lòng chờ\\, đừng tắt bot\\!_",
            total_ahead
        )

    # Polling chờ slot trống
    waited  = 0
    attempt = 0
    while True:
        if len(_processing) < MAX_SLOTS:
            break

        attempt += 1
        waited  += 5
        pos_now  = max(1, len(_processing))

        try:
            await status_cb(
                f"⌛ *ĐANG CHỜ SLOT TRỐNG*\n\n"
                f"```\n"
                f"  🔄 Đang xử lý: {len(_processing)}/{MAX_SLOTS}\n"
                f"  ⏱  Đã chờ:    {waited}s\n"
                f"  📍 Vị trí:    #{pos_now}\n"
                f"```",
                pos_now
            )
        except Exception:
            pass

        await asyncio.sleep(5)

        if waited > 600:  # timeout 10 phút
            if uid in _virtual_queue:
                _virtual_queue.remove(uid)
            return False

    # Đến lượt → chiếm slot
    if uid in _virtual_queue:
        _virtual_queue.remove(uid)
    _processing.add(uid)
    return True


def leave_queue(user_id: str):
    """Gọi sau khi xử lý xong hoặc lỗi để giải phóng slot."""
    uid = str(user_id)
    _processing.discard(uid)
    if uid in _virtual_queue:
        _virtual_queue.remove(uid)


def get_queue_info() -> dict:
    return {
        "processing":    list(_processing),
        "virtual_queue": list(_virtual_queue),
        "active_slots":  len(_processing),
    }