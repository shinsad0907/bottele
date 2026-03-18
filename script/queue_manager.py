"""
queue_manager.py
----------------
Hàng chờ FREE:
  - Hàng chờ ảo: random 1-4 người, mỗi người delay 10s
  - Nếu đang có người thật xử lý → nối tiếp thật (không fake)
  - VIP / VIP_PRO: bỏ qua hoàn toàn
"""
import asyncio
import logging
import random

log = logging.getLogger(__name__)

MAX_SLOTS    = 5
DELAY_PER_FAKE_PERSON = 10   # giây mỗi người fake

_virtual_queue: list[str] = []
_processing:    set[str]  = set()


def is_paid(package: str) -> bool:
    return package in ("vip", "vip_pro")


async def enter_queue(user_id: str, package: str, status_cb) -> bool:
    uid = str(user_id)

    # ── VIP / VIP_PRO: xử lý ngay, không hàng chờ ──
    if is_paid(package):
        _processing.add(uid)
        return True

    # ── FREE ──
    if uid not in _virtual_queue:
        _virtual_queue.append(uid)

    active_real = len(_processing)

    # Trường hợp 1: Không có ai đang xử lý → fake queue random 1-4 người
    if active_real == 0:
        fake_count = random.randint(1, 4)
        total_wait = fake_count * DELAY_PER_FAKE_PERSON

        await status_cb(
            f"⏳ *Đang kiểm tra hàng chờ\\.\\.\\.*\n\n"
            f"```\n"
            f"  👥 Trước bạn:  {fake_count} người đang xử lý\n"
            f"  ⏱  Ước tính:  ~{total_wait} giây\n"
            f"  🔄 Vui lòng chờ\\.\\.\\.\n"
            f"```",
            fake_count
        )

        # Đếm ngược từng người fake
        for i in range(fake_count, 0, -1):
            await asyncio.sleep(DELAY_PER_FAKE_PERSON)
            remaining = i - 1
            if remaining > 0:
                try:
                    await status_cb(
                        f"⏳ *Đang xử lý hàng chờ\\.\\.\\.*\n\n"
                        f"```\n"
                        f"  👥 Còn lại:   {remaining} người trước bạn\n"
                        f"  ⏱  Ước tính: ~{remaining * DELAY_PER_FAKE_PERSON} giây\n"
                        f"  🔄 Vui lòng chờ\\.\\.\\.\n"
                        f"```",
                        remaining
                    )
                except Exception:
                    pass

        # Fake xong → vào slot
        if uid in _virtual_queue:
            _virtual_queue.remove(uid)
        _processing.add(uid)

        try:
            await status_cb(
                f"✅ *ĐẾN LƯỢT BẠN\\!*\n\n"
                f"```\n"
                f"  🚀 Bắt đầu xử lý ngay\\.\\.\\.\n"
                f"```",
                0
            )
        except Exception:
            pass

        return True

    # Trường hợp 2: Có người thật đang xử lý → nối tiếp thật
    virtual_pos  = _virtual_queue.index(uid)
    total_ahead  = active_real + virtual_pos

    try:
        await status_cb(
            f"⏳ *ĐANG XẾP HÀNG CHỜ*\n\n"
            f"```\n"
            f"  📍 Vị trí:      #{total_ahead + 1}\n"
            f"  🔄 Đang xử lý:  {active_real}/{MAX_SLOTS} người\n"
            f"  ⏱  Ước tính:   ~{total_ahead * 40} giây\n"
            f"```\n\n"
            f"_Đừng tắt bot\\!_",
            total_ahead
        )
    except Exception:
        pass

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

        if waited > 600:
            if uid in _virtual_queue:
                _virtual_queue.remove(uid)
            return False

    if uid in _virtual_queue:
        _virtual_queue.remove(uid)
    _processing.add(uid)

    try:
        await status_cb(
            f"✅ *ĐẾN LƯỢT BẠN\\!*\n\n"
            f"```\n  🚀 Bắt đầu xử lý ngay\\.\\.\\.\n```",
            0
        )
    except Exception:
        pass

    return True


def leave_queue(user_id: str):
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