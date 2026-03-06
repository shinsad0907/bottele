import sys
import os
import time
import requests
import random
import string
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QLabel, QLineEdit, QTabWidget,
    QTextEdit, QProgressBar, QMessageBox, QSpinBox,
    QGroupBox, QListWidget, QScrollArea, QStatusBar,
    QDialog, QLayout, QTreeWidget, QTreeWidgetItem, QCheckBox
)
from PyQt5.QtGui import QPixmap, QFont, QColor
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRect, QSize, QPoint

# ═══════════════════════════════════════════════════════
#  STYLE
# ═══════════════════════════════════════════════════════
STYLE = """
QWidget {
    background: #0d0d1a; color: #e0e0f0;
    font-family: 'Segoe UI', sans-serif; font-size: 13px;
}
QTabWidget::pane { border: 1px solid #2a2a4a; border-radius: 8px; }
QTabBar::tab {
    background: #12122a; color: #666;
    padding: 9px 24px; margin-right: 2px; border-radius: 6px 6px 0 0;
}
QTabBar::tab:selected { background: #16213e; color: #00e5ff; border-bottom: 2px solid #00e5ff; }
QTabBar::tab:hover { color: #aae; }
QPushButton {
    background: #1a1a2e; border: 1px solid #2a2a4a;
    border-radius: 6px; padding: 6px 14px; color: #c0c0e0;
}
QPushButton:hover { background: #252545; border-color: #5555aa; color: #fff; }
QPushButton:disabled { color: #444; border-color: #1a1a1a; }
QPushButton#accentBtn {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0f3460,stop:1 #533483);
    border: none; color: #fff; font-weight: bold; font-size: 14px;
}
QPushButton#accentBtn:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1a4a80,stop:1 #6644aa);
}
QPushButton#greenBtn {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0a4a2a,stop:1 #1a7a3a);
    border: none; color: #fff; font-weight: bold;
}
QPushButton#greenBtn:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0d5e33,stop:1 #229944);
}
QLineEdit, QTextEdit, QListWidget {
    background: #12122a; border: 1px solid #2a2a4a;
    border-radius: 6px; padding: 4px; color: #dde;
    selection-background-color: #0f3460;
}
QListWidget::item { padding: 3px 6px; }
QListWidget::item:selected { background: #0f3460; border-radius: 4px; }
QTreeWidget {
    background: #10102a; border: 1px solid #2a2a4a;
    border-radius: 6px; color: #dde; alternate-background-color: #12122a;
}
QTreeWidget::item { padding: 4px 2px; }
QTreeWidget::item:selected { background: #1a2a4a; }
QHeaderView::section {
    background: #1a1a3a; color: #9090cc; padding: 5px;
    border: none; border-right: 1px solid #2a2a4a; font-weight: bold;
}
QScrollBar:vertical { background:#0d0d1a; width:8px; border-radius:4px; }
QScrollBar::handle:vertical { background:#2a2a5a; border-radius:4px; min-height:20px; }
QScrollBar:horizontal { background:#0d0d1a; height:8px; border-radius:4px; }
QScrollBar::handle:horizontal { background:#2a2a5a; border-radius:4px; min-width:20px; }
QProgressBar {
    background:#12122a; border:1px solid #2a2a4a; border-radius:6px;
    text-align:center; color:white; height:20px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #00b4d8,stop:1 #00e5ff);
    border-radius:6px;
}
QGroupBox {
    border:1px solid #2a2a4a; border-radius:8px;
    margin-top:10px; padding-top:8px; font-weight:bold; color:#9090cc;
}
QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 5px; }
QSpinBox { background:#12122a; border:1px solid #2a2a4a; border-radius:4px; color:#dde; padding:2px; }
QStatusBar { background:#0a0a18; color:#888; font-size:12px; }
QCheckBox { border:none; background:transparent; }
QCheckBox::indicator { width:16px; height:16px; }
QDialog { background:#0d0d1a; }
"""

STATUS_MAP = {
    "pending":    ("⏳", "#888888"),
    "account":    ("🔑", "#f0c040"),
    "uploading":  ("📤", "#40a0f0"),
    "processing": ("⚙️",  "#a040f0"),
    "done":       ("✅", "#40e080"),
    "error":      ("❌", "#f04040"),
}
STATUS_LABELS = {
    "pending":    "Chờ xử lý",
    "account":    "Tạo tài khoản",
    "uploading":  "Upload ảnh",
    "processing": "Xử lý AI",
    "done":       "Hoàn thành",
    "error":      "Lỗi",
}

FIREBASE_KEY = "AIzaSyDkChmbBT5DiK0HNTA8Ffx8NJq7reWkS6I"
TEMP_DOMAINS = ["getmule.com", "fivemail.com", "vomoto.com", "mailnull.com"]
FIREBASE_HDR = {
    'accept': '*/*', 'content-type': 'application/json',
    'origin': 'https://undresswith.ai',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'x-browser-channel': 'stable',
    'x-browser-copyright': 'Copyright 2026 Google LLC. All Rights reserved.',
    'x-browser-validation': 'aSLd2f09Ia/YwdnAvb1HwCexgog=',
    'x-browser-year': '2026',
    'x-client-data': 'CI+2yQEIpLbJAQipncoBCOr9ygEIlKHLAQiFoM0B',
    'x-client-version': 'Chrome/JsCore/11.0.1/FirebaseCore-web',
    'x-firebase-gmpid': '1:453358396684:web:3d416bb1f03907914e1529',
}
API_HDR = {
    'accept': '*/*', 'content-type': 'application/json',
    'origin': 'https://undresswith.ai', 'referer': 'https://undresswith.ai/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

# ═══════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════

def random_email():
    rnd = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    return f"{rnd}@{random.choice(TEMP_DOMAINS)}"

def create_account():
    email = random_email()
    r = requests.post(
        'https://identitytoolkit.googleapis.com/v1/accounts:signUp',
        params={'key': FIREBASE_KEY}, headers=FIREBASE_HDR,
        json={'returnSecureToken': True, 'email': email, 'password': email,
              'clientType': 'CLIENT_TYPE_WEB'}, timeout=15
    ).json()
    if 'idToken' not in r:
        raise Exception(f"Firebase: {r.get('error',{}).get('message', str(r))}")
    r2 = requests.post(
        'https://sv.aivideo123.site/api/user/init_data', headers=API_HDR,
        json={'token': r['idToken'], 'code': '-1', 'login_type': 0, 'current_uid': ''},
        timeout=15
    ).json()
    if r2.get('code') != 1:
        raise Exception(f"init_data: {r2}")
    return email, r2['data']['session_token']

# ═══════════════════════════════════════════════════════
#  MASTER WORKER  (account + inference per task)
# ═══════════════════════════════════════════════════════

class MasterWorker(QThread):
    tree_update  = pyqtSignal(str, str, str)      # task_id, status_key, detail
    result_ready = pyqtSignal(str, str, int, str) # image_path, url, var_idx, task_id
    progress     = pyqtSignal(int)
    log          = pyqtSignal(str)
    finished_all = pyqtSignal()

    def __init__(self, image_paths, prompt, variations):
        super().__init__()
        self.image_paths = image_paths
        self.prompt = prompt
        self.variations = variations
        self._stop = False

    def _run_task(self, task_id, image_path, var_idx):
        name = os.path.basename(image_path)
        try:
            self.tree_update.emit(task_id, "account", "Đang tạo tài khoản...")
            email, token = create_account()
            self.tree_update.emit(task_id, "account", f"✓ {email}")
            self.log.emit(f"[{name}#{var_idx+1}] 🔑 {email}")

            headers = {**API_HDR, "x-session-token": token}

            self.tree_update.emit(task_id, "uploading", "Đang upload ảnh...")
            fname = os.path.basename(image_path)
            r = requests.post(
                "https://sv.aivideo123.site/api/item/get_pre_url",
                headers=headers, json={"file_name": fname, "file_type": 0}, timeout=15
            ).json()
            if r["code"] != 1:
                raise Exception("get_pre_url thất bại")
            s3_url = r["data"]["url"]
            fields = r["data"]["fields"]
            s3_key = fields["key"]
            with open(image_path, "rb") as f:
                up = requests.post(s3_url, data=fields, files={"file": (fname, f)}, timeout=30)
            if up.status_code not in [200, 201, 204]:
                raise Exception(f"Upload lỗi {up.status_code}")
            self.tree_update.emit(task_id, "uploading", "✓ Upload xong")

            self.tree_update.emit(task_id, "processing", "Đang gọi AI...")
            inf = requests.post(
                "https://sv.aivideo123.site/api/item/inference2",
                headers=headers,
                json={"s3_path": s3_key, "mask_path": "", "prompt": self.prompt, "ai_model_type": 3},
                timeout=15
            ).json()
            if inf["code"] != 1:
                raise Exception("Inference thất bại")
            uid = inf["data"]["item"]["uid"]
            time_need = inf["data"]["item"]["time_need"]
            self.tree_update.emit(task_id, "processing", f"AI đang tạo ảnh...")
            time.sleep(time_need)

            r2 = requests.post(
                "https://sv.aivideo123.site/api/item/get_items",
                headers=headers, json={"page": 0, "page_size": 50}, timeout=15
            ).json()
            result_url = ""
            for item in r2["data"]["items"]:
                if item["uid"] == uid:
                    result_url = item.get("thumbnail", "")
                    break
            if not result_url:
                raise Exception("Không tìm thấy kết quả")

            self.tree_update.emit(task_id, "done", "✅ Hoàn thành")
            self.result_ready.emit(image_path, result_url, var_idx, task_id)
            self.log.emit(f"[{name}#{var_idx+1}] ✅ Xong")

        except Exception as e:
            self.tree_update.emit(task_id, "error", str(e))
            self.log.emit(f"[{name}#{var_idx+1}] ❌ {e}")

    def run(self):
        tasks = []
        for path in self.image_paths:
            for v in range(self.variations):
                tasks.append((f"{os.path.basename(path)}__v{v}", path, v))
        total = len(tasks)
        done = 0
        max_w = min(total, 20)
        self.log.emit(f"🚀 {len(self.image_paths)} ảnh × {self.variations} biến thể = {total} task ({max_w} luồng)")
        with ThreadPoolExecutor(max_workers=max_w) as ex:
            futures = {ex.submit(self._run_task, tid, p, v): tid for tid, p, v in tasks}
            for fut in as_completed(futures):
                if self._stop:
                    break
                done += 1
                self.progress.emit(int(done / total * 100))
        self.finished_all.emit()

    def stop(self):
        self._stop = True

# ═══════════════════════════════════════════════════════
#  IMAGE LOADER
# ═══════════════════════════════════════════════════════

class ImageLoader(QThread):
    done = pyqtSignal(bytes)
    def __init__(self, url):
        super().__init__()
        self.url = url
    def run(self):
        try:
            self.done.emit(requests.get(self.url, timeout=20).content)
        except:
            pass

# ═══════════════════════════════════════════════════════
#  BULK SAVE WORKER
# ═══════════════════════════════════════════════════════

class BulkSaveWorker(QThread):
    progress = pyqtSignal(int, int)  # done, total
    done     = pyqtSignal(int, str)  # saved_count, folder

    def __init__(self, cards, folder):
        super().__init__()
        self.cards = cards
        self.folder = folder

    def run(self):
        total = len(self.cards)
        saved = 0
        for card in self.cards:
            # wait up to 30s for image data
            waited = 0
            while card._img_data is None and waited < 30:
                time.sleep(0.5)
                waited += 0.5
            if card._img_data:
                base = os.path.splitext(card.image_name)[0]
                fpath = os.path.join(self.folder, f"{base}_v{card.variation+1}.jpg")
                n = 1
                while os.path.exists(fpath):
                    fpath = os.path.join(self.folder, f"{base}_v{card.variation+1}_{n}.jpg")
                    n += 1
                with open(fpath, "wb") as f:
                    f.write(card._img_data)
                saved += 1
            self.progress.emit(saved, total)
        self.done.emit(saved, self.folder)

# ═══════════════════════════════════════════════════════
#  PREVIEW DIALOG
# ═══════════════════════════════════════════════════════

class PreviewDialog(QDialog):
    def __init__(self, img_data, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(900, 800)
        self.setStyleSheet("background:#0d0d1a;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none; background:#0d0d1a;")
        lbl = QLabel()
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("background:#0d0d1a; border:none;")
        pix = QPixmap()
        pix.loadFromData(img_data)
        lbl.setPixmap(pix)
        scroll.setWidget(lbl)
        lay.addWidget(scroll)
        btn = QPushButton("✕  Đóng")
        btn.setFixedHeight(36)
        btn.clicked.connect(self.accept)
        lay.addWidget(btn)

# ═══════════════════════════════════════════════════════
#  RESULT CARD
# ═══════════════════════════════════════════════════════

class ResultCard(QWidget):
    selection_changed = pyqtSignal()

    def __init__(self, image_name, variation, url, parent=None):
        super().__init__(parent)
        self.image_name = image_name
        self.variation = variation
        self.url = url
        self._img_data = None
        self._selected = False

        self.setFixedWidth(230)
        self._refresh_border()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        # Top row: checkbox + name
        top = QHBoxLayout()
        self.chk = QCheckBox()
        self.chk.stateChanged.connect(self._on_check)
        top.addWidget(self.chk)
        lbl_n = QLabel(f"<b>{image_name}</b><br>"
                       f"<span style='color:#888;font-size:11px'>Biến thể #{variation+1}</span>")
        lbl_n.setStyleSheet("border:none; background:transparent; color:#ccd;")
        top.addWidget(lbl_n, 1)
        lay.addLayout(top)

        # Image preview
        self.img_lbl = QLabel("⏳")
        self.img_lbl.setAlignment(Qt.AlignCenter)
        self.img_lbl.setFixedSize(210, 210)
        self.img_lbl.setStyleSheet(
            "border:1px solid #333; border-radius:8px; background:#0d0d1a; color:#555; font-size:28px;")
        self.img_lbl.mousePressEvent = lambda e: self._preview()
        lay.addWidget(self.img_lbl, alignment=Qt.AlignCenter)

        self.btn_view = QPushButton("🔍  Xem to")
        self.btn_view.setEnabled(False)
        self.btn_view.setFixedHeight(28)
        self.btn_view.clicked.connect(self._preview)
        lay.addWidget(self.btn_view)

        self.btn_dl = QPushButton("⬇️  Tải riêng")
        self.btn_dl.setObjectName("greenBtn")
        self.btn_dl.setEnabled(False)
        self.btn_dl.setFixedHeight(28)
        self.btn_dl.clicked.connect(self._download_single)
        lay.addWidget(self.btn_dl)

        self._loader = ImageLoader(url)
        self._loader.done.connect(self._on_loaded)
        self._loader.start()

    def _refresh_border(self):
        if self._selected:
            self.setStyleSheet("ResultCard { background:#1a2a4a; border:2px solid #00e5ff; border-radius:10px; }")
        else:
            self.setStyleSheet("ResultCard { background:#16213e; border:1px solid #2a2a5a; border-radius:10px; }")

    def _on_check(self, state):
        self._selected = bool(state)
        self._refresh_border()
        self.selection_changed.emit()

    def is_selected(self):
        return self._selected

    def set_selected(self, val):
        self.chk.setChecked(val)

    def _on_loaded(self, data):
        self._img_data = data
        pix = QPixmap()
        pix.loadFromData(data)
        self.img_lbl.setPixmap(pix.scaled(210, 210, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.img_lbl.setToolTip("Click để xem to")
        self.btn_view.setEnabled(True)
        self.btn_dl.setEnabled(True)

    def _preview(self):
        if self._img_data:
            PreviewDialog(self._img_data, f"{self.image_name} — #{self.variation+1}", self).exec_()

    def _download_single(self):
        if not self._img_data:
            return
        base = os.path.splitext(self.image_name)[0]
        path, _ = QFileDialog.getSaveFileName(
            self, "Lưu ảnh", f"{base}_v{self.variation+1}.jpg", "Images (*.jpg *.png)")
        if path:
            with open(path, "wb") as f:
                f.write(self._img_data)
            QMessageBox.information(self, "✅ Đã lưu", path)

# ═══════════════════════════════════════════════════════
#  FLOW LAYOUT
# ═══════════════════════════════════════════════════════

class FlowLayout(QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []

    def addItem(self, item): self._items.append(item)
    def count(self): return len(self._items)
    def itemAt(self, i): return self._items[i] if 0 <= i < len(self._items) else None
    def takeAt(self, i): return self._items.pop(i) if 0 <= i < len(self._items) else None
    def removeWidget(self, w):
        for i, it in enumerate(self._items):
            if it.widget() is w:
                self._items.pop(i); break
    def hasHeightForWidth(self): return True
    def heightForWidth(self, w): return self._do_layout(QRect(0, 0, w, 0), True)
    def setGeometry(self, rect): super().setGeometry(rect); self._do_layout(rect, False)
    def sizeHint(self): return self.minimumSize()
    def minimumSize(self):
        s = QSize()
        for it in self._items: s = s.expandedTo(it.minimumSize())
        return s
    def _do_layout(self, rect, test):
        x, y, row_h, gap = rect.x()+8, rect.y()+8, 0, 12
        for it in self._items:
            iw, ih = it.sizeHint().width(), it.sizeHint().height()
            if x + iw > rect.right()-8 and row_h > 0:
                x = rect.x()+8; y += row_h+gap; row_h = 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), it.sizeHint()))
            x += iw+gap; row_h = max(row_h, ih)
        return y + row_h - rect.y() + 8

# ═══════════════════════════════════════════════════════
#  MAIN WINDOW
# ═══════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("✨ AI Clothes Tool Pro")
        self.resize(1200, 820)
        self.setStyleSheet(STYLE)

        self.image_paths   = []
        self.master_worker = None
        self._bulk_worker  = None
        self._cards        = []
        self._tree_items   = {}

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Sẵn sàng")

        self.setCentralWidget(self._build_ui())

    # ───────────────────────────── UI ─────────────────────────────

    def _build_ui(self):
        root = QWidget()
        root_lay = QHBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)
        root_lay.addWidget(self._build_left())
        root_lay.addWidget(self._build_right(), 1)
        return root

    def _build_left(self):
        left = QWidget()
        left.setFixedWidth(340)
        left.setStyleSheet("QWidget{background:#0a0a16;}")
        lv = QVBoxLayout(left)
        lv.setContentsMargins(16, 16, 16, 16)
        lv.setSpacing(10)

        title = QLabel("✨ AI Clothes Tool Pro")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet("color:#00e5ff; background:transparent; border:none;")
        lv.addWidget(title)

        # Prompt
        grp_p = QGroupBox("✍️  Prompt trang phục")
        pv = QVBoxLayout(grp_p)
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("VD: wear a red summer dress...")
        pv.addWidget(self.prompt_input)
        lv.addWidget(grp_p)

        # Images
        grp_i = QGroupBox("🖼️  Ảnh đầu vào")
        iv = QVBoxLayout(grp_i)
        brow = QHBoxLayout()
        for txt, fn in [("➕ Thêm ảnh", self._add_files),
                        ("📁 Folder",   self._add_folder),
                        ("🗑️ Xóa",      self._clear_images)]:
            b = QPushButton(txt); b.clicked.connect(fn); brow.addWidget(b)
        iv.addLayout(brow)
        self.img_list = QListWidget()
        self.img_list.setMaximumHeight(110)
        iv.addWidget(self.img_list)
        self.lbl_count = QLabel("0 ảnh đã chọn")
        self.lbl_count.setStyleSheet("color:#888; font-size:11px; background:transparent; border:none;")
        iv.addWidget(self.lbl_count)
        lv.addWidget(grp_i)

        # Settings
        grp_s = QGroupBox("⚙️  Cài đặt")
        sv = QHBoxLayout(grp_s)
        sv.addWidget(QLabel("Số biến thể / ảnh:"))
        self.spin_var = QSpinBox()
        self.spin_var.setRange(1, 10)
        self.spin_var.setValue(1)
        self.spin_var.setFixedWidth(60)
        sv.addWidget(self.spin_var)
        sv.addStretch()
        note = QLabel("(= tài khoản mới)")
        note.setStyleSheet("color:#555; font-size:11px; border:none; background:transparent;")
        sv.addWidget(note)
        lv.addWidget(grp_s)

        # Start / Stop
        self.btn_start = QPushButton("🚀  Bắt đầu")
        self.btn_start.setObjectName("accentBtn")
        self.btn_start.setFixedHeight(44)
        self.btn_start.clicked.connect(self._start)
        lv.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹  Dừng")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setFixedHeight(34)
        self.btn_stop.clicked.connect(self._stop)
        lv.addWidget(self.btn_stop)

        self.progress = QProgressBar()
        lv.addWidget(self.progress)

        # Log
        grp_log = QGroupBox("📋  Log")
        log_v = QVBoxLayout(grp_log)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        log_v.addWidget(self.log_box)
        lv.addWidget(grp_log)

        lv.addStretch()
        return left

    def _build_right(self):
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_tree_tab(),    "📊  Tiến trình")
        self.tabs.addTab(self._build_preview_tab(), "🖼️  Kết quả")
        rv.addWidget(self.tabs)
        return right

    def _build_tree_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        hdr = QHBoxLayout()
        lbl = QLabel("📊  Tiến trình xử lý")
        lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        lbl.setStyleSheet("color:#00e5ff; border:none; background:transparent;")
        hdr.addWidget(lbl)
        hdr.addStretch()
        btn_clr = QPushButton("🗑️  Xóa log")
        btn_clr.clicked.connect(self._clear_tree)
        hdr.addWidget(btn_clr)
        v.addLayout(hdr)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Ảnh", "Biến thể", "Trạng thái", "Chi tiết"])
        self.tree.setColumnWidth(0, 200)
        self.tree.setColumnWidth(1, 80)
        self.tree.setColumnWidth(2, 140)
        self.tree.setColumnWidth(3, 340)
        self.tree.setAlternatingRowColors(True)
        v.addWidget(self.tree)
        return w

    def _build_preview_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(6)

        # Row 1: title + count
        row1 = QHBoxLayout()
        lbl = QLabel("🖼️  Kết quả")
        lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        lbl.setStyleSheet("color:#00e5ff; border:none; background:transparent;")
        row1.addWidget(lbl)
        row1.addStretch()
        self.lbl_res_count = QLabel("0 kết quả")
        self.lbl_res_count.setStyleSheet("color:#888; font-size:12px; border:none; background:transparent;")
        row1.addWidget(self.lbl_res_count)
        v.addLayout(row1)

        # Row 2: bulk action buttons
        row2 = QHBoxLayout()
        self.btn_sel_all  = QPushButton("☑️  Chọn tất cả")
        self.btn_sel_none = QPushButton("☐  Bỏ chọn")
        self.lbl_sel_count = QLabel("0 đã chọn")
        self.lbl_sel_count.setStyleSheet("color:#aaa; font-size:12px; border:none; background:transparent;")
        self.btn_save_sel = QPushButton("⬇️  Lưu đã chọn")
        self.btn_save_sel.setObjectName("accentBtn")
        self.btn_save_all = QPushButton("💾  Lưu tất cả")
        self.btn_save_all.setObjectName("greenBtn")
        self.btn_clr_res  = QPushButton("🗑️  Xóa")

        self.btn_sel_all.clicked.connect(lambda: self._select_all(True))
        self.btn_sel_none.clicked.connect(lambda: self._select_all(False))
        self.btn_save_sel.clicked.connect(self._save_selected)
        self.btn_save_all.clicked.connect(self._save_all)
        self.btn_clr_res.clicked.connect(self._clear_results)

        for ww in [self.btn_sel_all, self.btn_sel_none, self.lbl_sel_count,
                   self.btn_save_sel, self.btn_save_all, self.btn_clr_res]:
            row2.addWidget(ww)
        row2.addStretch()
        v.addLayout(row2)

        # Save progress bar (hidden until saving)
        self.save_progress = QProgressBar()
        self.save_progress.setVisible(False)
        self.save_progress.setFixedHeight(14)
        self.save_progress.setTextVisible(True)
        v.addWidget(self.save_progress)

        # Card grid
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border:none; background:#0d0d1a;")
        self.cards_w = QWidget()
        self.cards_w.setStyleSheet("background:transparent;")
        self.cards_flow = FlowLayout(self.cards_w)
        self.scroll.setWidget(self.cards_w)
        v.addWidget(self.scroll)

        return w

    # ───────────────────────────── IMAGE ACTIONS ─────────────────────────────

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn ảnh", "", "Images (*.png *.jpg *.jpeg *.webp)")
        for f in files:
            if f not in self.image_paths:
                self.image_paths.append(f)
                self.img_list.addItem(os.path.basename(f))
        self._upd_count()

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn folder")
        if not folder:
            return
        for fn in sorted(os.listdir(folder)):
            if os.path.splitext(fn)[1].lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                fp = os.path.join(folder, fn)
                if fp not in self.image_paths:
                    self.image_paths.append(fp)
                    self.img_list.addItem(fn)
        self._upd_count()

    def _clear_images(self):
        self.image_paths.clear()
        self.img_list.clear()
        self._upd_count()

    def _upd_count(self):
        self.lbl_count.setText(f"{len(self.image_paths)} ảnh đã chọn")

    # ───────────────────────────── PROCESS ─────────────────────────────

    def _start(self):
        if not self.image_paths:
            QMessageBox.warning(self, "Lỗi", "Chưa chọn ảnh nào!")
            return
        if not self.prompt_input.text().strip():
            QMessageBox.warning(self, "Lỗi", "Nhập prompt trước!")
            return

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress.setValue(0)
        self.log_box.clear()
        self.tree.clear()
        self._tree_items.clear()
        self.tabs.setCurrentIndex(0)

        variations = self.spin_var.value()
        for path in self.image_paths:
            name = os.path.basename(path)
            for v in range(variations):
                task_id = f"{name}__v{v}"
                icon, color = STATUS_MAP["pending"]
                item = QTreeWidgetItem([name, f"#{v+1}", f"{icon} Chờ xử lý", ""])
                item.setForeground(2, QColor(color))
                self.tree.addTopLevelItem(item)
                self._tree_items[task_id] = item

        self.master_worker = MasterWorker(list(self.image_paths), self.prompt_input.text().strip(), variations)
        self.master_worker.tree_update.connect(self._on_tree_update)
        self.master_worker.result_ready.connect(self._on_result)
        self.master_worker.progress.connect(self.progress.setValue)
        self.master_worker.log.connect(self.log_box.append)
        self.master_worker.finished_all.connect(self._on_done)
        self.master_worker.start()
        self.status_bar.showMessage("⏳ Đang xử lý...")

    def _stop(self):
        if self.master_worker:
            self.master_worker.stop()
            self.log_box.append("⏹ Đang dừng...")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _on_tree_update(self, task_id, status_key, detail):
        item = self._tree_items.get(task_id)
        if not item:
            return
        icon, color = STATUS_MAP.get(status_key, ("•", "#888"))
        label = STATUS_LABELS.get(status_key, status_key)
        item.setText(2, f"{icon} {label}")
        item.setText(3, detail)
        item.setForeground(2, QColor(color))
        self.tree.scrollToItem(item)

    def _on_result(self, image_path, url, var_idx, task_id):
        card = ResultCard(os.path.basename(image_path), var_idx, url)
        card.selection_changed.connect(self._upd_sel_count)
        self._cards.append(card)
        self.cards_flow.addWidget(card)
        self.cards_w.adjustSize()
        n = len(self._cards)
        self.lbl_res_count.setText(f"{n} kết quả")
        self.tabs.setTabText(1, f"🖼️  Kết quả ({n})")

    def _on_done(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        n = len(self._cards)
        self.status_bar.showMessage(f"✅ Xong! {n} kết quả")
        self.tabs.setCurrentIndex(1)
        QMessageBox.information(self, "✅ Hoàn thành", f"Đã xong!\n{n} kết quả.")

    # ───────────────────────────── SELECTION & SAVE ─────────────────────────────

    def _upd_sel_count(self):
        n = sum(1 for c in self._cards if c.is_selected())
        self.lbl_sel_count.setText(f"{n} đã chọn")

    def _select_all(self, val):
        for c in self._cards:
            c.set_selected(val)
        self._upd_sel_count()

    def _save_selected(self):
        selected = [c for c in self._cards if c.is_selected()]
        if not selected:
            QMessageBox.warning(self, "Chưa chọn", "Tick checkbox trên card trước!")
            return
        self._bulk_save(selected)

    def _save_all(self):
        if not self._cards:
            QMessageBox.information(self, "Thông báo", "Chưa có kết quả nào!")
            return
        self._bulk_save(list(self._cards))

    def _bulk_save(self, cards):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu ảnh")
        if not folder:
            return

        self.save_progress.setVisible(True)
        self.save_progress.setValue(0)
        self.save_progress.setMaximum(len(cards))
        self.btn_save_all.setEnabled(False)
        self.btn_save_sel.setEnabled(False)

        self._bulk_worker = BulkSaveWorker(cards, folder)
        self._bulk_worker.progress.connect(self._on_bulk_progress)
        self._bulk_worker.done.connect(self._on_bulk_done)
        self._bulk_worker.start()

    def _on_bulk_progress(self, done, total):
        self.save_progress.setValue(done)
        self.save_progress.setFormat(f"Đang lưu {done}/{total}...")
        self.status_bar.showMessage(f"💾 Đang lưu... {done}/{total}")

    def _on_bulk_done(self, saved, folder):
        self.save_progress.setVisible(False)
        self.btn_save_all.setEnabled(True)
        self.btn_save_sel.setEnabled(True)
        self.status_bar.showMessage(f"✅ Đã lưu {saved} ảnh")
        QMessageBox.information(self, "✅ Lưu xong", f"Đã lưu {saved} ảnh vào:\n{folder}")

    # ───────────────────────────── CLEAR ─────────────────────────────

    def _clear_tree(self):
        self.tree.clear()
        self._tree_items.clear()

    def _clear_results(self):
        for c in self._cards:
            self.cards_flow.removeWidget(c)
            c.deleteLater()
        self._cards.clear()
        self.lbl_res_count.setText("0 kết quả")
        self.lbl_sel_count.setText("0 đã chọn")
        self.tabs.setTabText(1, "🖼️  Kết quả")
        self.cards_w.adjustSize()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())