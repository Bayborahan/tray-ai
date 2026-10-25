from PyQt6.QtCore import QObject, QEvent

class NoWheelEventFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            event.ignore()
            return True
        return super().eventFilter(obj, event)

import sys
import os

if getattr(sys, 'frozen', False):
    BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
    if not os.path.exists(os.path.join(BASE_DIR, "lang")):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        if os.path.exists(os.path.join(exe_dir, "lang")):
            BASE_DIR = exe_dir
        elif os.path.exists(os.path.join(exe_dir, "_internal", "lang")):
            BASE_DIR = os.path.join(exe_dir, "_internal")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import json
import time
import socket
import psutil
import subprocess
import requests
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSystemTrayIcon, QMenu, QTabWidget,
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSlider,
    QPushButton, QFileDialog, QListWidget, QListWidgetItem, QCheckBox,
    QLineEdit, QSpinBox, QDoubleSpinBox, QProgressBar, QMessageBox, 
    QScrollArea, QFrame, QGroupBox, QPlainTextEdit, QGridLayout,
    QInputDialog, QStackedWidget, QSplitter, QDialog, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, QPoint, QThread, pyqtSignal, QTimer, QLocale
from PyQt6.QtGui import QTextCursor, QIcon, QAction, QColor, QPixmap, QCursor, QGuiApplication, QPainter, QBrush

from core.cache_manager import CacheManager
from core.gguf_parser import analyze_gguf_file, estimate_memory_usage_gb
from core.server_manager import ServerManager, TelemetryPoller
from core.hardware import get_system_hardware, read_drm_vram_used_gb
from core.hf_downloader import HFSearchWorker, HFFilesWorker, DownloadWorker
from core.engine_updater import EngineVersionChecker, EngineUpdateWorker
from core.api_gateway import APIGatewayServer
from core.whisper_manager import AudioRecorder, TranscribeWorker, WhisperDownloadWorker, WHISPER_MODELS_DIR
from ui.styles import DARK_STYLE

USER_ENGINES_DIR = os.path.expanduser("~/.local/share/tray-ai/engines")
os.makedirs(USER_ENGINES_DIR, exist_ok=True)

search_dirs = [
    os.path.join(BASE_DIR, "engines"),
    "/opt/tray-ai/engines"
]
for sdir in search_dirs:
    if os.path.isdir(sdir):
        import shutil
        for ef in ["llama-server", "whisper-cli"]:
            src = os.path.join(sdir, ef)
            dst = os.path.join(USER_ENGINES_DIR, ef)
            if os.path.exists(src) and not os.path.exists(dst):
                try:
                    shutil.copy2(src, dst)
                    os.chmod(dst, 0o755)
                except Exception:
                    pass

CONFIG_DIR = os.path.expanduser("~/.config/tray-ai")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
ICON_PATH = os.path.join(BASE_DIR, "assets", "tray-ai.svg")

LANG_DIR = os.path.join(BASE_DIR, "lang")

def load_lang_dict(lang_code):
    fpath = os.path.join(LANG_DIR, f"{lang_code}.json")
    if os.path.exists(fpath):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    fallback_path = os.path.join(LANG_DIR, "en.json")
    if os.path.exists(fallback_path):
        try:
            with open(fallback_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return default

def save_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except:
        pass

def get_tray_icon(state="ready"):
    colors = {
        "ready": "#7aa2f7",
        "loading": "#e0af68",
        "active": "#9ece6a",
        "generating": "#bb9af7",
        "stopped": "#f7768e"
    }
    color_hex = colors.get(state, "#7aa2f7")
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor(color_hex)))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(2, 2, 28, 28)
    p.setBrush(QBrush(QColor("#1a1b26")))
    p.drawEllipse(7, 7, 18, 18)
    p.setBrush(QBrush(QColor(color_hex)))
    p.drawEllipse(12, 12, 8, 8)
    p.end()
    return QIcon(pixmap)

from ui.chat_dialog import ChatTesterDialog


class VoiceAssistantDialog(QDialog):
    def __init__(self, parent, engines_dir, gateway_port):
        super().__init__(parent)
        self.engines_dir = engines_dir
        self.gateway_port = gateway_port
        self.setWindowTitle("🎙️ Yerel Whisper Sesli Asistan")
        self.resize(520, 560)
        self.setStyleSheet(DARK_STYLE)

        self.recorder = AudioRecorder()
        self.model_path = os.path.join(WHISPER_MODELS_DIR, "ggml-base.bin")

        l = QVBoxLayout(self)
        l.setSpacing(10)

        # Üst Bilgi Kartı
        top_frame = QFrame()
        top_frame.setStyleSheet("background: #1f2335; border: 1px solid #3b4261; border-radius: 8px; padding: 8px;")
        v_top = QVBoxLayout(top_frame)
        self.lbl_model_status = QLabel()
        self.lbl_model_status.setStyleSheet("font-size: 12px; color: #7dcfff;")
        v_top.addWidget(self.lbl_model_status)

        self.btn_dl_model = QPushButton("⬇️ Whisper Modelini İndir (~140 MB)")
        self.btn_dl_model.setStyleSheet("background: #7aa2f7; color: #15161e; font-weight: bold;")
        self.btn_dl_model.clicked.connect(self.download_whisper_model)
        v_top.addWidget(self.btn_dl_model)
        l.addWidget(top_frame)

        # Bas-Konuş Mikrofon Alanı
        mid_frame = QFrame()
        mid_frame.setStyleSheet("background: #16161e; border: 1px solid #292e42; border-radius: 8px; padding: 12px;")
        v_mid = QVBoxLayout(mid_frame)
        v_mid.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_mic_status = QLabel("Konuşmak için butona basılı tutun")
        self.lbl_mic_status.setStyleSheet("color: #a9b1d6; font-size: 13px; font-weight: bold;")
        v_mid.addWidget(self.lbl_mic_status, alignment=Qt.AlignmentFlag.AlignCenter)

        self.btn_mic = QPushButton("🎙️ BAS - KONUŞ")
        self.btn_mic.setFixedSize(220, 55)
        self.btn_mic.setStyleSheet("background: #7aa2f7; color: #15161e; font-size: 15px; font-weight: bold; border-radius: 27px;")
        self.btn_mic.pressed.connect(self.start_talking)
        self.btn_mic.released.connect(self.stop_talking)
        v_mid.addWidget(self.btn_mic, alignment=Qt.AlignmentFlag.AlignCenter)
        l.addWidget(mid_frame)

        # Seçenekler
        opt_box = QHBoxLayout()
        self.chk_auto_ask = QCheckBox("Metni doğrudan aktif LLM'e sor")
        self.chk_auto_ask.setChecked(True)
        self.chk_copy_clip = QCheckBox("Panoya Kopyala")
        self.chk_copy_clip.setChecked(True)
        opt_box.addWidget(self.chk_auto_ask)
        opt_box.addWidget(self.chk_copy_clip)
        l.addLayout(opt_box)

        # Konuşulan Metin ve Model Cevabı
        l.addWidget(QLabel("<b>Duyulan / Transkript:</b>"))
        self.txt_transcript = QPlainTextEdit()
        self.txt_transcript.setFixedHeight(70)
        self.txt_transcript.setPlaceholderText("Konuştuğunuz cümle burada belirecek...")
        l.addWidget(self.txt_transcript)

        l.addWidget(QLabel("<b>Yapay Zeka Cevabı:</b>"))
        self.txt_response = QPlainTextEdit()
        self.txt_response.setReadOnly(True)
        self.txt_response.setStyleSheet("background: #13141c; color: #9ece6a; font-family: sans-serif;")
        l.addWidget(self.txt_response, 1)

        self.check_model_state()

    def check_model_state(self):
        if os.path.exists(self.model_path):
            self.lbl_model_status.setText(f"✓ Whisper Modeli Hazır: ggml-base.bin ({round(os.path.getsize(self.model_path)/(1024*1024))} MB)")
            self.btn_dl_model.hide()
            self.btn_mic.setEnabled(True)
        else:
            self.lbl_model_status.setText("⚠️ Whisper modeli bulunamadı. Lütfen modeli indirin.")
            self.btn_dl_model.show()
            self.btn_mic.setEnabled(False)

    def download_whisper_model(self):
        self.btn_dl_model.setEnabled(False)
        self.lbl_model_status.setText("⏳ Model indiriliyor...")
        self.dl_worker = WhisperDownloadWorker(self.model_path)
        self.dl_worker.progress.connect(lambda p, m: self.lbl_model_status.setText(f"⏳ {m} (%{p})"))
        self.dl_worker.finished_ok.connect(lambda: (self.check_model_state(), QMessageBox.information(self, "Whisper", "Model hazır!")))
        self.dl_worker.error.connect(lambda e: (self.lbl_model_status.setText(f"❌ {e}"), self.btn_dl_model.setEnabled(True)))
        self.dl_worker.start()

    def start_talking(self):
        try:
            self.recorder.start_recording()
            self.btn_mic.setText("🔴 DİNLİYOR...")
            self.btn_mic.setStyleSheet("background: #f7768e; color: #15161e; font-size: 15px; font-weight: bold; border-radius: 27px;")
            self.lbl_mic_status.setText("Dinleniyor... Bıraktığınızda çözümlenecek.")
        except Exception as e:
            QMessageBox.warning(self, "Ses Hatası", str(e))

    def stop_talking(self):
        self.recorder.stop_recording()
        self.btn_mic.setText("⏳ ÇÖZÜMLENİYOR...")
        self.btn_mic.setStyleSheet("background: #e0af68; color: #15161e; font-size: 14px; font-weight: bold; border-radius: 27px;")
        self.lbl_mic_status.setText("Whisper sesi metne dönüştürüyor...")

        self.trans_worker = TranscribeWorker(self.engines_dir, self.model_path, lang="tr")
        self.trans_worker.finished_text.connect(self.on_transcribed)
        self.trans_worker.error.connect(self.on_transcribe_error)
        self.trans_worker.start()

    def on_transcribed(self, text):
        self.btn_mic.setText("🎙️ BAS - KONUŞ")
        self.btn_mic.setStyleSheet("background: #7aa2f7; color: #15161e; font-size: 15px; font-weight: bold; border-radius: 27px;")
        self.lbl_mic_status.setText("Tamamlandı!")
        self.txt_transcript.setPlainText(text)

        if self.chk_copy_clip.isChecked() and text:
            QApplication.clipboard().setText(text)

        if self.chk_auto_ask.isChecked() and text:
            self.ask_llm(text)

    def on_transcribe_error(self, err):
        self.btn_mic.setText("🎙️ BAS - KONUŞ")
        self.btn_mic.setStyleSheet("background: #7aa2f7; color: #15161e; font-size: 15px; font-weight: bold; border-radius: 27px;")
        self.lbl_mic_status.setText(f"⚠️ {err}")

    def ask_llm(self, prompt):
        self.txt_response.setPlainText("⏳ Aktif yapay zeka modeline soruluyor...")
        port = self.gateway_port
        url = f"http://127.0.0.1:{port}/v1/chat/completions"

        def _worker():
            try:
                r = requests.post(
                    url,
                    json={"messages": [{"role": "user", "content": prompt}], "stream": False},
                    timeout=120
                )
                if r.status_code == 200:
                    ans = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                    QTimer.singleShot(0, lambda: self.txt_response.setPlainText(ans))
                else:
                    QTimer.singleShot(0, lambda: self.txt_response.setPlainText(f"Hata: {r.status_code} - {r.text}"))
            except Exception as e:
                QTimer.singleShot(0, lambda: self.txt_response.setPlainText(f"Bağlantı Hatası: {e}"))

        import threading
        threading.Thread(target=_worker, daemon=True).start()


class MetadataInspectorDialog(QDialog):
    def __init__(self, parent, model_info):
        super().__init__(parent)
        self.setWindowTitle(f"🔍 GGUF Metadata & Mimari Müfettişi — {model_info.get('filename', '')}")
        self.resize(700, 880)
        self.setStyleSheet(DARK_STYLE)

        layout = QVBoxLayout(self)
        extra = model_info.get("extra_meta", {})

        moe_str = f"{extra.get('expert_used_count', 0)} / {extra.get('expert_count', 0)} Aktif Uzman (MoE)" if extra.get("expert_count", 0) > 0 else "Dense (Standart Yoğun Model)"
        mtp_str = f"<span style='color:#9ece6a;'>✓ Var ({model_info.get('mtp_layers', 1)} Katman - {extra.get('mtp_reason', 'Aktif')})</span>" if model_info.get("has_mtp") else "<span style='color:#f7768e;'>Yok</span>"
        yarn_str = f"<span style='color:#9ece6a;'>✓ Destekleniyor ({extra.get('yarn_reason', 'Aktif')})</span>" if model_info.get("has_yarn") else "Standart RoPE"

        summary = QLabel(
            f"<b>Model Adı:</b> {extra.get('general_name') or model_info['filename']}  |  <b>Yayıncı:</b> {model_info.get('publisher', 'Bilinmiyor')}<br>"
            f"<b>Mimari:</b> <span style='color:#7dcfff;'>{model_info['arch'].upper()}</span>  |  "
            f"<b>Tip:</b> <span style='color:#bb9af7;'>{moe_str}</span>  |  "
            f"<b>Tensor Sayısı:</b> {extra.get('tensor_count', 0)}<br>"
            f"<b>Katman (Blocks):</b> {model_info['total_layers']}  |  "
            f"<b>Embedding:</b> {extra.get('embed_length', 0)}  |  "
            f"<b>FFN Boyutu:</b> {extra.get('feed_forward_length', 0)}<br>"
            f"<b>Attention Heads (Q / KV):</b> {extra.get('head_count', 0)} / {extra.get('head_count_kv', 0)}  |  "
            f"<b>Head Boyutu (K/V):</b> {extra.get('key_length', 128)} / {extra.get('value_length', 128)}<br>"
            f"<b>RoPE Base / Scale:</b> {extra.get('rope_freq_base', 10000):,.1f} / {extra.get('rope_scale', 1.0)} ({extra.get('rope_scaling_type', 'none')})<br>"
            f"<b>MTP (Multi-Token):</b> {mtp_str}  |  <b>YaRN / Uzun Bağlam:</b> {yarn_str}<br>"
            f"<b>Önerilen Sampler ({extra.get('sampler_source', 'Profil')}):</b> "
            f"<span style='color:#e0af68;'>Temp: {model_info.get('recommended_temp', 0.7)} | Top-P: {model_info.get('recommended_topp', 0.9)} | Min-P: {model_info.get('recommended_minp', 0.05)} | Top-K: {model_info.get('recommended_top_k', 40)}</span>"
        )
        summary.setWordWrap(True)
        summary.setStyleSheet("background: #1f2335; border: 1px solid #3b4261; padding: 10px; border-radius: 6px; font-size: 12px;")
        layout.addWidget(summary)

        tabs = QTabWidget()
        
        tab_kv = QWidget()
        v_kv = QVBoxLayout(tab_kv)
        search_input = QLineEdit()
        search_input.setPlaceholderText("🔎 Metadata anahtarı veya değeri ara (örn: rope, mtp, nextn, attention, sampling)...")
        v_kv.addWidget(search_input)

        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Metadata Anahtarı (Key)", "Değer (Value)"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        all_kv = extra.get("all_kv", {})
        table.setRowCount(len(all_kv))
        for row_idx, (k, v) in enumerate(sorted(all_kv.items())):
            table.setItem(row_idx, 0, QTableWidgetItem(str(k)))
            table.setItem(row_idx, 1, QTableWidgetItem(str(v)))
        v_kv.addWidget(table)

        def filter_table(txt):
            t_low = txt.lower()
            for r in range(table.rowCount()):
                k_item = table.item(r, 0).text().lower()
                v_item = table.item(r, 1).text().lower()
                table.setRowHidden(r, t_low not in k_item and t_low not in v_item)

        search_input.textChanged.connect(filter_table)
        tabs.addTab(tab_kv, f"📋 Tüm Metadata Alanları ({len(all_kv)})")

        tab_tpl = QWidget()
        v_tpl = QVBoxLayout(tab_tpl)
        txt_tpl = QPlainTextEdit()
        txt_tpl.setReadOnly(True)
        txt_tpl.setStyleSheet("background: #13141c; color: #73daca; font-family: monospace; font-size: 11px;")
        txt_tpl.setPlainText(extra.get("chat_template") or "Bu modelde gömülü tokenizer.chat_template bulunamadı.")
        v_tpl.addWidget(txt_tpl)
        tabs.addTab(tab_tpl, "💬 Jinja Chat Şablonu (Template)")

        layout.addWidget(tabs, 1)

        btn_close = QPushButton("Kapat / Close")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


class FastScannerThread(QThread):
    new_model_found = pyqtSignal(dict)
    scan_finished = pyqtSignal()

    def __init__(self, folder_path, cache_mgr):
        super().__init__()
        self.folder_path = folder_path
        self.cache_mgr = cache_mgr

    def run(self):
        if not self.folder_path or not os.path.isdir(self.folder_path):
            self.scan_finished.emit()
            return

        for root, _, files in os.walk(self.folder_path):
            for file in files:
                f_low = file.lower()
                # mmproj dosyalarını bağımsız bir dil modeli gibi listelemeyi engelle
                if f_low.endswith(".gguf") and not f_low.startswith("mmproj") and "mmproj" not in f_low:
                    full_path = os.path.join(root, file)
                    mtime = os.path.getmtime(full_path)
                    cached = self.cache_mgr.get_model(full_path, mtime)
                    if cached:
                        self.new_model_found.emit(cached)
                    else:
                        info = analyze_gguf_file(full_path)
                        self.cache_mgr.save_model(info)
                        self.new_model_found.emit(info)

        self.scan_finished.emit()


class DownloadItemWidget(QFrame):
    def __init__(self, task_id, filename, repo_id, worker):
        super().__init__()
        self.task_id = task_id
        self.worker = worker
        self.setStyleSheet("background: #24283b; border: 1px solid #3b4261; border-radius: 6px; padding: 6px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        top = QHBoxLayout()
        self.lbl_title = QLabel(f"<b>{filename}</b> <span style='color:#7aa2f7; font-size:11px;'>({repo_id})</span>")
        self.lbl_title.setWordWrap(True)
        self.lbl_stats = QLabel("0.0 MB / ? MB (0.0 MB/s)")
        self.lbl_stats.setStyleSheet("color: #73daca; font-size: 11px;")
        top.addWidget(self.lbl_title, 1)
        top.addWidget(self.lbl_stats)
        layout.addLayout(top)

        self.prog = QProgressBar()
        self.prog.setRange(0, 100)
        self.prog.setValue(0)
        self.prog.setFixedHeight(14)
        layout.addWidget(self.prog)

        btns = QHBoxLayout()
        self.lbl_state = QLabel("⏳ İndiriliyor...")
        self.lbl_state.setStyleSheet("font-size: 11px; color: #e0af68;")
        self.btn_pause = QPushButton("⏸ Duraklat")
        self.btn_pause.setFixedHeight(26)
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.btn_cancel = QPushButton("✕ İptal")
        self.btn_cancel.setFixedHeight(26)
        self.btn_cancel.setStyleSheet("background: #f7768e; color: #15161e; font-weight: bold;")
        self.btn_cancel.clicked.connect(self.cancel_dl)

        btns.addWidget(self.lbl_state)
        btns.addStretch()
        btns.addWidget(self.btn_pause)
        btns.addWidget(self.btn_cancel)
        layout.addLayout(btns)

        self._paused = False

    def toggle_pause(self):
        if not self._paused:
            self._paused = True
            self.worker.pause()
            self.btn_pause.setText("▶ Devam Et")
            self.lbl_state.setText("⏸ Duraklatıldı")
        else:
            self._paused = False
            self.worker.resume()
            self.btn_pause.setText("⏸ Duraklat")
            self.lbl_state.setText("⏳ İndiriliyor...")

    def cancel_dl(self):
        self.worker.cancel()
        self.btn_pause.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.lbl_state.setText("🚫 İptal Edildi")


class TrayAIApp(QMainWindow):
    def __init__(self, runner_ref):
        super().__init__()
        self.runner_ref = runner_ref
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.resize(740, 880)
        self.setStyleSheet(DARK_STYLE)
        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))

        self._drag_pos = None
        self.cfg = load_json(CONFIG_FILE, {
            "last_folder": "",
            "enabled_gpus": {},
            "port": 8080,
            "language": "auto",
            "hf_token": "",
            "per_model_cfg": {}
        })

        self.current_lang = self._resolve_language(self.cfg.get("language", "auto"))
        self.cache_mgr = CacheManager()
        self.server_mgr = ServerManager(engines_dir=USER_ENGINES_DIR)
        
        self.server_service_enabled = True
        self.loaded_models = {}
        self.selected_model_path = None
        self.selected_draft_path = None
        self.active_model_info = None
        self.gpu_toggles = {}
        self.remote_tool_active = False
        self.active_downloads = {}

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.main_layout = QVBoxLayout(main_widget)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(6)

        top_bar = QHBoxLayout()
        self.lbl_title = QLabel()
        self.lbl_title.setStyleSheet("font-size: 15px; color: #7aa2f7;")
        self.status_lbl = QLabel()
        self.status_lbl.setStyleSheet("color: #7dcfff; font-weight: bold;")
        
        btn_frameless_style = """
            QPushButton {
                background: transparent;
                border: none;
                color: #a9b1d6;
                font-size: 16px;
                border-radius: 6px;
                padding: 2px;
            }
            QPushButton:hover {
                background: rgba(122, 162, 247, 0.15);
                color: #7dcfff;
            }
        """
        btn_close_frameless_style = """
            QPushButton {
                background: transparent;
                border: none;
                color: #7a829e;
                font-size: 15px;
                font-weight: bold;
                border-radius: 6px;
                padding: 2px;
            }
            QPushButton:hover {
                background: rgba(247, 118, 142, 0.18);
                color: #f7768e;
            }
        """
        self.btn_chat_tester = QPushButton("💬")
        self.btn_chat_tester.setFixedSize(28, 28)
        self.btn_chat_tester.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_chat_tester.setStyleSheet(btn_frameless_style)
        self.btn_chat_tester.setToolTip("Model Test Sohbeti (Mini Playground)")
        self.btn_chat_tester.clicked.connect(self.open_chat_tester)

        self.btn_voice_assistant = QPushButton("🎙️")
        self.btn_voice_assistant.setFixedSize(28, 28)
        self.btn_voice_assistant.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_voice_assistant.setStyleSheet(btn_frameless_style)
        self.btn_voice_assistant.setToolTip("Sesli Asistan (Whisper Bas-Konuş)")
        self.btn_voice_assistant.clicked.connect(self.open_voice_assistant)

        self.btn_settings = QPushButton("⚙️")
        self.btn_settings.setFixedSize(28, 28)
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.setStyleSheet(btn_frameless_style)
        self.btn_settings.setToolTip("Uygulama Ayarları / Application Settings")
        self.btn_settings.clicked.connect(self.toggle_settings_view)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(btn_close_frameless_style)
        btn_close.setToolTip("Pencereyi Kapat")
        btn_close.clicked.connect(self.hide)

        top_bar.addWidget(self.lbl_title)
        top_bar.addStretch()
        top_bar.addWidget(self.status_lbl)
        top_bar.addWidget(self.btn_chat_tester)
        top_bar.addWidget(self.btn_voice_assistant)
        top_bar.addWidget(self.btn_settings)
        top_bar.addWidget(btn_close)
        self.main_layout.addLayout(top_bar)

        self.view_stack = QStackedWidget()
        self.main_layout.addWidget(self.view_stack, 1)

        self.tabs = QTabWidget()
        self.view_stack.addWidget(self.tabs)

        self.init_tab_models()
        self.init_tab_config()
        self.init_tab_hardware()
        self.init_tab_server()
        self.init_tab_hf()
        self.init_tab_downloads()

        self.init_settings_page()

        # ============================================================
        # ENTEGRE ALT KONSOL (UNIFIED BOTTOM DOCK & HUD)
        # ============================================================
        bottom_dock = QFrame()
        bottom_dock.setStyleSheet("""
            QFrame#bottomDock {
                background: #16161e;
                border: 1px solid #292e42;
                border-top: 2px solid #3b4261;
                border-radius: 10px;
                padding: 6px;
            }
        """)
        bottom_dock.setObjectName("bottomDock")
        v_dock = QVBoxLayout(bottom_dock)
        v_dock.setContentsMargins(10, 8, 10, 8)
        v_dock.setSpacing(6)

        # 1. Satır: İstemci Durum Rozeti + Üretim Hızı + Kes Butonu
        h_hud_top = QHBoxLayout()
        self.lbl_tel_phase = QLabel()
        self.lbl_tel_phase.setStyleSheet("color: #a9b1d6; font-size: 12px; font-weight: 500;")

        self.lbl_tel_speed = QLabel(self.t("speed_prefix").format(val="0.0"))
        self.lbl_tel_speed.setStyleSheet("""
            background: #1f2335;
            color: #73daca;
            font-weight: bold;
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 5px;
            border: 1px solid #3b4261;
        """)

        self.btn_abort_gen = QPushButton("🛑")
        self.btn_abort_gen.setFixedSize(28, 26)
        self.btn_abort_gen.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_abort_gen.setToolTip("Mevcut üretimi yarıda kes")
        self.btn_abort_gen.setStyleSheet("""
            QPushButton {
                background: #24283b;
                border: 1px solid #414868;
                color: #f7768e;
                font-size: 11px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: #f7768e;
                color: #15161e;
            }
        """)
        self.btn_abort_gen.clicked.connect(self.abort_current_generation)

        h_hud_top.addWidget(self.lbl_tel_phase, 1)
        h_hud_top.addWidget(self.lbl_tel_speed)
        h_hud_top.addWidget(self.btn_abort_gen)
        v_dock.addLayout(h_hud_top)

        # 2. Satır: Dijital Sayaç Rozetleri (Prompt % / Token / Ctx)
        h_counters = QHBoxLayout()
        h_counters.setSpacing(6)

        counter_style = """
            QLabel {
                background: #1a1e2d;
                border: 1px solid #292e42;
                border-radius: 5px;
                padding: 3px 6px;
                font-size: 11px;
            }
        """

        self.lbl_prompt_read = QLabel("📖 Prompt: %0")
        self.lbl_prompt_read.setStyleSheet(counter_style + "QLabel { color: #7dcfff; font-weight: bold; }")

        self.lbl_token_counter = QLabel("🔢 Token: 0")
        self.lbl_token_counter.setStyleSheet(counter_style + "QLabel { color: #bb9af7; font-weight: bold; }")

        self.lbl_ctx_usage = QLabel("📦 Ctx: 0 / 0")
        self.lbl_ctx_usage.setStyleSheet(counter_style + "QLabel { color: #e0af68; }")

        h_counters.addWidget(self.lbl_prompt_read, 1)
        h_counters.addWidget(self.lbl_token_counter, 1)
        h_counters.addWidget(self.lbl_ctx_usage, 1)
        v_dock.addLayout(h_counters)

        # 3. İnce Prompt Akış Çizgisi
        self.bar_prompt_activity = QProgressBar()
        self.bar_prompt_activity.setRange(0, 100)
        self.bar_prompt_activity.setValue(0)
        self.bar_prompt_activity.setFixedHeight(4)
        self.bar_prompt_activity.setTextVisible(False)
        self.bar_prompt_activity.setStyleSheet("""
            QProgressBar { background: #1f2335; border: none; border-radius: 2px; }
            QProgressBar::chunk { background: #bb9af7; border-radius: 2px; }
        """)
        v_dock.addWidget(self.bar_prompt_activity)

        # 4. Model Yükleme Durumu & İnce Yükleme Barı
        h_load_info = QHBoxLayout()
        self.lbl_load_stage = QLabel()
        self.lbl_load_stage.setStyleSheet("font-size: 11px; color: #7aa2f7;")
        h_load_info.addWidget(self.lbl_load_stage)
        v_dock.addLayout(h_load_info)

        self.load_progress_bar = QProgressBar()
        self.load_progress_bar.setRange(0, 100)
        self.load_progress_bar.setValue(0)
        self.load_progress_bar.setFixedHeight(5)
        self.load_progress_bar.setTextVisible(False)
        self.load_progress_bar.setStyleSheet("""
            QProgressBar { background: #1f2335; border: none; border-radius: 2px; }
            QProgressBar::chunk { background: #9ece6a; border-radius: 2px; }
        """)
        v_dock.addWidget(self.load_progress_bar)

        # 5. Ergonomik Eylem Butonları Barı
        h_actions = QHBoxLayout()
        h_actions.setSpacing(8)

        self.btn_load_model = QPushButton()
        self.btn_load_model.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_load_model.setFixedHeight(36)
        self.btn_load_model.setStyleSheet("""
            QPushButton {
                background: #9ece6a;
                color: #15161e;
                font-size: 12px;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 4px 14px;
            }
            QPushButton:hover {
                background: #b9f27c;
            }
            QPushButton:disabled {
                background: #24283b;
                color: #565f89;
            }
        """)
        self.btn_load_model.clicked.connect(self.load_selected_model)

        self.btn_unload_model = QPushButton()
        self.btn_unload_model.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_unload_model.setFixedHeight(36)
        self.btn_unload_model.setEnabled(False)
        self.btn_unload_model.setStyleSheet("""
            QPushButton {
                background: #1f2335;
                border: 1px solid #f7768e;
                color: #f7768e;
                font-size: 11px;
                font-weight: bold;
                border-radius: 6px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background: #f7768e;
                color: #15161e;
            }
            QPushButton:disabled {
                border-color: #3b4261;
                color: #565f89;
                background: #16161e;
            }
        """)
        self.btn_unload_model.clicked.connect(self.unload_current_model)

        self.btn_drop_cache = QPushButton()
        self.btn_drop_cache.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_drop_cache.setFixedHeight(36)
        self.btn_drop_cache.setStyleSheet("""
            QPushButton {
                background: #1f2335;
                border: 1px solid #3b4261;
                color: #7aa2f7;
                font-size: 11px;
                font-weight: 500;
                border-radius: 6px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background: #24283b;
                border-color: #7aa2f7;
                color: #7dcfff;
            }
        """)
        self.btn_drop_cache.clicked.connect(self.flush_system_ram_cache)

        h_actions.addWidget(self.btn_load_model, 3)
        h_actions.addWidget(self.btn_unload_model, 2)
        h_actions.addWidget(self.btn_drop_cache, 2)
        v_dock.addLayout(h_actions)

        self.main_layout.addWidget(bottom_dock)

        self.res_timer = QTimer(self)
        self.res_timer.timeout.connect(self.update_resource_monitor)
        self.res_timer.start(2000)
        self.load_tracker_timer = QTimer(self)
        self.load_tracker_timer.timeout.connect(self._track_model_loading_progress)

        user_port = int(self.cfg.get("port", 8080))
        self.upstream_port = user_port + 1

        self.poller = TelemetryPoller(port=self.upstream_port)
        self.poller.health_ready.connect(self.on_health_confirmed_ready)
        self.poller.loading_tick.connect(self.on_health_loading_tick)
        self.poller.telemetry_update.connect(self.on_live_telemetry)
        self.poller.start()

        # Dinamik API Gateway'i Başlat
        self.api_gateway = APIGatewayServer(
            host="0.0.0.0" if self.chk_lan.isChecked() else "127.0.0.1",
            port=user_port,
            upstream_port=self.upstream_port,
            get_all_models_func=self.get_gateway_models_list,
            get_active_model_id_func=self.get_current_active_model_id
        )
        self.api_gateway.log_signal.connect(lambda msg: self.txt_logs.appendPlainText(f"[Gateway] {msg}"))
        self.api_gateway.sig_switch_model.connect(self.on_gateway_request_switch_model)
        self.api_gateway.start()

        self.apply_language()

        last_dir = self.cfg.get("last_folder", "")
        if last_dir and os.path.isdir(last_dir):
            self.lbl_folder.setText(f".../{os.path.basename(last_dir)}")
            self.load_from_sqlite_instant(last_dir)

        QTimer.singleShot(600, lambda: self.fetch_hf_models(mode="trending"))

    def _resolve_language(self, lang_setting):
        if lang_setting in ("tr", "en"):
            return lang_setting
        sys_loc = QLocale.system().name().lower()
        return "tr" if sys_loc.startswith("tr") else "en"

    def t(self, key, default=None):
        if not hasattr(self, "_lang_cache") or self._cached_lang != self.current_lang:
            self._lang_cache = load_lang_dict(self.current_lang)
            self._cached_lang = self.current_lang
        val = self._lang_cache.get(key)
        if val is None:
            return default if default is not None else key
        return val

    def set_status_badge(self, state, text=None):
        styles = {
            "waiting": "background: rgba(122, 162, 247, 0.12); color: #7aa2f7; border: 1px solid rgba(122, 162, 247, 0.4);",
            "loading": "background: rgba(224, 175, 104, 0.12); color: #e0af68; border: 1px solid rgba(224, 175, 104, 0.4);",
            "ready": "background: rgba(158, 206, 106, 0.14); color: #9ece6a; border: 1px solid rgba(158, 206, 106, 0.45);",
            "stopped": "background: rgba(247, 118, 142, 0.12); color: #f7768e; border: 1px solid rgba(247, 118, 142, 0.4);",
            "unloaded": "background: rgba(125, 207, 255, 0.12); color: #7dcfff; border: 1px solid rgba(125, 207, 255, 0.4);",
            "error": "background: rgba(247, 118, 142, 0.20); color: #f7768e; border: 1px solid #f7768e;"
        }
        st = styles.get(state, styles["waiting"])
        self.status_lbl.setStyleSheet(f"border-radius: 13px; padding: 4px 12px; font-weight: bold; font-size: 11px; {st}")
        if text:
            self.status_lbl.setText(text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 45:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def init_settings_page(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        page = QWidget()
        l = QVBoxLayout(page)
        l.setSpacing(12)

        top_row = QHBoxLayout()
        self.lbl_settings_header = QLabel()
        self.lbl_settings_header.setStyleSheet("font-size: 16px; color: #bb9af7;")
        self.btn_back_main = QPushButton()
        self.btn_back_main.clicked.connect(lambda: self.view_stack.setCurrentIndex(0))
        top_row.addWidget(self.lbl_settings_header)
        top_row.addStretch()
        top_row.addWidget(self.btn_back_main)
        l.addLayout(top_row)

        grp_runtime = QGroupBox("⚡ Runtime & Engines (llama.cpp Motor Yönetimi ve Güncelleme)")
        v_rt = QVBoxLayout(grp_runtime)
        v_rt.setSpacing(8)

        self.chk_auto_update_eng = QCheckBox("Auto-update Runtime Engines (Başlangıçta güncellemeleri denetle)")
        self.chk_auto_update_eng.setChecked(self.cfg.get("auto_update_engine", True))
        self.chk_auto_update_eng.toggled.connect(self.save_auto_update_pref)
        v_rt.addWidget(self.chk_auto_update_eng)

        h_rt_top = QHBoxLayout()
        self.cb_update_channel = QComboBox()
        self.cb_update_channel.addItem("Kaynak Koddan Derle (Native Build - Önerilen)", "build")
        self.cb_update_channel.addItem("Hazır Paket İndir (GitHub Release Binary)", "download")
        h_rt_top.addWidget(self.cb_update_channel, 1)

        self.btn_check_eng_updates = QPushButton("🔄 Check for updates")
        self.btn_check_eng_updates.setFixedWidth(155)
        self.btn_check_eng_updates.clicked.connect(self.check_engine_updates)
        h_rt_top.addWidget(self.btn_check_eng_updates)
        v_rt.addLayout(h_rt_top)

        self.rt_cards_layout = QVBoxLayout()
        v_rt.addLayout(self.rt_cards_layout)

        self.lbl_eng_update_status = QLabel("Motor sürüm bilgisi için 'Check for updates' butonuna tıklayın.")
        self.lbl_eng_update_status.setStyleSheet("color: #7dcfff; font-size: 11px;")
        v_rt.addWidget(self.lbl_eng_update_status)

        self.prog_eng_update = QProgressBar()
        self.prog_eng_update.setRange(0, 100)
        self.prog_eng_update.setValue(0)
        self.prog_eng_update.setFixedHeight(14)
        self.prog_eng_update.hide()
        v_rt.addWidget(self.prog_eng_update)

        l.addWidget(grp_runtime)

        self.grp_set_lang = QGroupBox()
        v_lang = QVBoxLayout(self.grp_set_lang)
        h_lang = QHBoxLayout()
        self.lbl_ui_lang = QLabel()
        self.cb_lang = QComboBox()
        self.cb_lang.addItem("Sistem Dili / Auto", "auto")
        self.cb_lang.addItem("Türkçe (TR)", "tr")
        self.cb_lang.addItem("English (EN)", "en")
        saved_l = self.cfg.get("language", "auto")
        idx = self.cb_lang.findData(saved_l)
        if idx >= 0:
            self.cb_lang.setCurrentIndex(idx)
        self.cb_lang.currentIndexChanged.connect(self.on_language_combo_changed)
        h_lang.addWidget(self.lbl_ui_lang)
        h_lang.addWidget(self.cb_lang, 1)
        v_lang.addLayout(h_lang)
        l.addWidget(self.grp_set_lang)

        self.grp_set_sys = QGroupBox()
        v_sys = QVBoxLayout(self.grp_set_sys)
        self.chk_autostart = QCheckBox()
        autostart_file = os.path.expanduser("~/.config/autostart/tray-ai.desktop")
        self.chk_autostart.setChecked(os.path.exists(autostart_file))
        self.chk_autostart.toggled.connect(self.toggle_autostart)
        v_sys.addWidget(self.chk_autostart)

        self.btn_install_desktop = QPushButton()
        self.btn_install_desktop.clicked.connect(self.register_desktop_icon)
        v_sys.addWidget(self.btn_install_desktop)
        l.addWidget(self.grp_set_sys)

        self.grp_set_hf = QGroupBox()
        v_hf = QVBoxLayout(self.grp_set_hf)
        self.lbl_hf_token = QLabel()
        self.input_hf_token = QLineEdit()
        self.input_hf_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_hf_token.setPlaceholderText("hf_...")
        self.input_hf_token.setText(self.cfg.get("hf_token", ""))
        self.input_hf_token.textChanged.connect(self.save_hf_token)
        v_hf.addWidget(self.lbl_hf_token)
        v_hf.addWidget(self.input_hf_token)
        l.addWidget(self.grp_set_hf)

        l.addStretch()
        scroll.setWidget(page)
        self.view_stack.addWidget(scroll)

        self.populate_runtime_cards({
            "local_main": "Kontrol ediliyor...",
            "latest_tag": "...",
            "assets": {},
            "has_vulkan": True,
            "has_rocm": os.path.exists("/opt/rocm"),
            "has_cuda": False
        })
        if self.cfg.get("auto_update_engine", True):
            QTimer.singleShot(1200, self.check_engine_updates)

    def save_auto_update_pref(self, checked):
        self.cfg["auto_update_engine"] = checked
        save_json(CONFIG_FILE, self.cfg)

    def check_engine_updates(self):
        self.lbl_eng_update_status.setText("⏳ GitHub üzerinden en güncel llama.cpp sürümleri sorgulanıyor...")
        self.btn_check_eng_updates.setEnabled(False)
        self.eng_checker = EngineVersionChecker(USER_ENGINES_DIR)
        self.eng_checker.version_info_ready.connect(self.on_engine_versions_ready)
        self.eng_checker.error_occurred.connect(lambda e: self.lbl_eng_update_status.setText(f"⚠️ {e}"))
        self.eng_checker.start()

    def on_engine_versions_ready(self, info):
        self.btn_check_eng_updates.setEnabled(True)
        self.latest_engine_info = info
        self.lbl_eng_update_status.setText(
            f"✅ Son Resmi Sürüm: {info['latest_tag']} ({info['published_at']})  |  Yerel Motor: {info['local_main']}"
        )
        self.populate_runtime_cards(info)

    def populate_runtime_cards(self, info):
        while self.rt_cards_layout.count():
            child = self.rt_cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        engines_meta = [
            {
                "key": "vulkan",
                "title": "Vulkan llama.cpp (Linux)",
                "desc": "Vulkan accelerated llama.cpp engine (AMD / Intel / NVIDIA GPU & iGPU)",
                "local_ver": info.get("local_main", ""),
                "compat": info.get("has_vulkan", True)
            },
            {
                "key": "cpu",
                "title": "CPU llama.cpp (Linux)",
                "desc": "CPU-only llama.cpp engine (AVX2 / AVX-512)",
                "local_ver": info.get("local_main", ""),
                "compat": True
            },
            {
                "key": "rocm",
                "title": "ROCm llama.cpp (Linux)",
                "desc": "AMD ROCm / HIP accelerated llama.cpp engine",
                "local_ver": info.get("local_main", ""),
                "compat": info.get("has_rocm", False)
            },
            {
                "key": "cuda",
                "title": "CUDA llama.cpp (Linux)",
                "desc": "NVIDIA CUDA accelerated llama.cpp engine",
                "local_ver": info.get("local_main", ""),
                "compat": info.get("has_cuda", False)
            }
        ]

        latest_tag = info.get("latest_tag", "Latest")
        assets = info.get("assets", {})

        for em in engines_meta:
            card = QFrame()
            card.setStyleSheet("background: #1f2335; border: 1px solid #292e42; border-radius: 6px; padding: 6px;")
            h = QHBoxLayout(card)
            h.setContentsMargins(8, 6, 8, 6)

            v_text = QVBoxLayout()
            ver_badge = f"<span style='background:#292e42; color:#7dcfff; padding:2px 6px; border-radius:4px; font-size:11px;'>{em['local_ver']} → {latest_tag}</span>"
            lbl_t = QLabel(f"<b>⚡ {em['title']}</b><br>{ver_badge}")
            lbl_t.setWordWrap(True)
            lbl_d = QLabel(f"<span style='color:#a9b1d6; font-size:11px;'>{em['desc']}</span>")
            lbl_d.setWordWrap(True)
            v_text.addWidget(lbl_t)
            v_text.addWidget(lbl_d)
            h.addLayout(v_text, 1)

            if em["compat"]:
                lbl_c = QLabel("<span style='color:#9ece6a; font-size:11px; font-weight:bold;'>✓ Compatible</span>")
            else:
                lbl_c = QLabel("<span style='color:#f7768e; font-size:11px; font-weight:bold;'>⚠️ Non Compatible</span>")
            h.addWidget(lbl_c)

            asset_info = assets.get(em["key"], assets.get("vulkan", {}))
            size_str = f" ({asset_info['size_mb']} MB)" if asset_info and "size_mb" in asset_info else ""
            btn_upd = QPushButton(f"Update{size_str}")
            btn_upd.setFixedHeight(28)
            btn_upd.setStyleSheet("background: #3b4261; color: #c0caf5; font-weight: bold; padding: 4px 10px;")
            url = asset_info.get("url", "") if asset_info else ""
            btn_upd.clicked.connect(lambda _, k=em["key"], u=url: self.start_engine_update(k, u))
            h.addWidget(btn_upd)

            self.rt_cards_layout.addWidget(card)

    def start_engine_update(self, target_key, asset_url):
        if self.server_mgr.is_running():
            self.unload_current_model()

        mode = self.cb_update_channel.currentData()
        self.prog_eng_update.show()
        self.prog_eng_update.setValue(5)
        self.lbl_eng_update_status.setText(f"⏳ {target_key.upper()} motoru güncelleniyor...")

        self.eng_updater = EngineUpdateWorker(
            engines_dir=USER_ENGINES_DIR,
            target_type=target_key,
            mode=mode,
            asset_url=asset_url,
        )
        self.eng_updater.progress_msg.connect(self.on_eng_update_progress)
        self.eng_updater.finished_ok.connect(self.on_eng_update_finished)
        self.eng_updater.error_occurred.connect(self.on_eng_update_error)
        self.eng_updater.start()

    def on_eng_update_progress(self, pct, msg):
        self.prog_eng_update.setValue(pct)
        self.lbl_eng_update_status.setText(msg)

    def on_eng_update_finished(self, target_key):
        self.prog_eng_update.setValue(100)
        self.lbl_eng_update_status.setText(f"✅ {target_key.upper()} motoru en son sürüme güncellendi!")
        self.check_engine_updates()

    def on_eng_update_error(self, err):
        self.prog_eng_update.hide()
        self.lbl_eng_update_status.setText(f"❌ Güncelleme Hatası: {err}")
        QMessageBox.warning(self, "Engine Update Error", err)

    def notify_desktop(self, title, message, icon_type="info"):
        tray = getattr(self.runner_ref, "tray", None) if hasattr(self, "runner_ref") else None
        if not tray:
            return

        icon_map = {
            "info": QSystemTrayIcon.MessageIcon.Information,
            "warning": QSystemTrayIcon.MessageIcon.Warning,
            "error": QSystemTrayIcon.MessageIcon.Critical
        }
        msg_icon = icon_map.get(icon_type, QSystemTrayIcon.MessageIcon.Information)
        tray.showMessage(title, message, msg_icon, 4000)

    def open_chat_tester(self):
        user_port = self.spin_port.value()
        dlg = ChatTesterDialog(self, user_port, self.get_current_active_model_id)
        dlg.exec()

    def open_voice_assistant(self):
        user_port = self.spin_port.value()
        dlg = VoiceAssistantDialog(self, USER_ENGINES_DIR, user_port)
        dlg.exec()

    def toggle_settings_view(self):
        if self.view_stack.currentIndex() == 0:
            self.view_stack.setCurrentIndex(1)
        else:
            self.view_stack.setCurrentIndex(0)

    def on_language_combo_changed(self):
        lang_code = self.cb_lang.currentData()
        self.cfg["language"] = lang_code
        save_json(CONFIG_FILE, self.cfg)
        self.current_lang = self._resolve_language(lang_code)
        if hasattr(self, "_cached_lang"):
            self._cached_lang = None
        self.apply_language()
        if hasattr(self, "refresh_model_list_view"):
            self.refresh_model_list_view()

    def toggle_autostart(self, enabled):
        autostart_dir = os.path.expanduser("~/.config/autostart")
        autostart_file = os.path.join(autostart_dir, "tray-ai.desktop")
        if enabled:
            os.makedirs(autostart_dir, exist_ok=True)
            content = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Tray AI Server\n"
                f"Exec={os.path.join(BASE_DIR, 'run.sh')}\n"
                f"Icon={ICON_PATH}\n"
                "Terminal=false\n"
                "X-GNOME-Autostart-enabled=true\n"
            )
            with open(autostart_file, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            if os.path.exists(autostart_file):
                os.remove(autostart_file)

    def register_desktop_icon(self):
        apps_dir = os.path.expanduser("~/.local/share/applications")
        os.makedirs(apps_dir, exist_ok=True)
        desk_file = os.path.join(apps_dir, "tray-ai.desktop")
        content = (
            "[Desktop Entry]\n"
            "Version=1.0\n"
            "Type=Application\n"
            "Name=Tray AI Server\n"
            "Comment=Local GGUF LLM Server in System Tray\n"
            f"Exec={os.path.join(BASE_DIR, 'run.sh')}\n"
            f"Icon={ICON_PATH}\n"
            "Terminal=false\n"
            "Categories=Development;ArtificialIntelligence;Utility;\n"
        )
        with open(desk_file, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(desk_file, 0o755)
        QMessageBox.information(self, "Tray AI", "✅ Uygulama simgesi Linux menüsüne başarıyla kaydedildi!")

    def save_hf_token(self, text):
        self.cfg["hf_token"] = text.strip()
        save_json(CONFIG_FILE, self.cfg)

    def flush_system_ram_cache(self):
        if self.server_mgr.is_running():
            QMessageBox.warning(self, "Tray AI", "Model şu anda bellekte aktif! Lütfen önce modeli boşaltın (UNLOAD).")
            return

        mem_before = round(psutil.virtual_memory().used / (1024**3), 2)
        pwd, ok = QInputDialog.getText(
            self,
            self.t("pwd_title"),
            self.t("pwd_prompt"),
            QLineEdit.EchoMode.Password
        )
        if not ok or not pwd:
            return

        try:
            proc = subprocess.run(
                ["sudo", "-S", "-k", "sh", "-c", "sync && echo 3 > /proc/sys/vm/drop_caches"],
                input=pwd + "\n",
                text=True,
                capture_output=True,
                timeout=15
            )
            if proc.returncode == 0:
                import time
                time.sleep(0.3)
                mem_after = round(psutil.virtual_memory().used / (1024**3), 2)
                diff = round(max(0.0, mem_before - mem_after), 2)
                self.update_resource_monitor()
                QMessageBox.information(
                    self,
                    self.t("ram_freed_title"),
                    self.t("ram_freed_msg").format(before=mem_before, after=mem_after, diff=diff)
                )
            else:
                err_detail = (proc.stderr or "").strip()
                QMessageBox.warning(self, self.t("pwd_title"), f"{self.t('ram_err_msg')}\n\n{err_detail}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def abort_current_generation(self):
        if self.server_mgr.is_running() and self.selected_model_path:
            self.load_selected_model()

    def init_tab_models(self):
        tab = QWidget()
        l = QVBoxLayout(tab)
        l.setSpacing(6)

        top_btn = QHBoxLayout()
        self.btn_select_dir = QPushButton()
        self.btn_select_dir.clicked.connect(self.choose_model_folder)
        self.btn_rescan = QPushButton()
        self.btn_rescan.clicked.connect(self.force_rescan_models)
        self.lbl_folder = QLabel()
        top_btn.addWidget(self.btn_select_dir)
        top_btn.addWidget(self.btn_rescan)
        top_btn.addWidget(self.lbl_folder)
        top_btn.addStretch()

        self.btn_open_folder = QPushButton("📁 Klasörü Aç")
        self.btn_open_folder.setToolTip("Model klasörünü dosya yöneticisinde açar")
        self.btn_open_folder.clicked.connect(self.open_root_folder_in_file_manager)
        top_btn.addWidget(self.btn_open_folder)
        l.addLayout(top_btn)

        filter_bar = QHBoxLayout()
        self.input_model_search = QLineEdit()
        self.input_model_search.setClearButtonEnabled(True)
        self.input_model_search.setPlaceholderText("🔎 Yerel modellerde ara (isim, mimari, quant)...")
        self.input_model_search.textChanged.connect(self.refresh_model_list_view)
        filter_bar.addWidget(self.input_model_search, 2)

        self.cb_model_filter = QComboBox()
        self.cb_model_filter.addItems([
            "Tüm Modeller",
            "⚡ MTP Destekliler",
            "🧶 YaRN Destekliler",
            "🧠 Düşünen (Reasoning)",
            "🔧 Araç / Ajan (Tools)",
            "🧩 MoE Modeller",
            "👁️ Görsel (Vision)"
        ])
        self.cb_model_filter.currentIndexChanged.connect(self.refresh_model_list_view)
        filter_bar.addWidget(self.cb_model_filter, 1)

        self.cb_model_sort = QComboBox()
        self.cb_model_sort.addItems([
            "İsme Göre (A-Z)",
            "Boyuta Göre (Küçükten Büyüğe)",
            "Boyuta Göre (Büyükten Küçüğe)",
            "Bağlama Göre (Max Ctx)"
        ])
        self.cb_model_sort.currentIndexChanged.connect(self.refresh_model_list_view)
        filter_bar.addWidget(self.cb_model_sort, 1)
        l.addLayout(filter_bar)

        self.lbl_models_summary = QLabel("Toplam: 0 model")
        self.lbl_models_summary.setStyleSheet("color: #7aa2f7; font-size: 11px;")
        l.addWidget(self.lbl_models_summary)

        self.list_models = QListWidget()
        self.list_models.setWordWrap(True)
        self.list_models.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_models.itemClicked.connect(self.on_model_selected)
        self.list_models.itemDoubleClicked.connect(self.on_model_double_clicked)
        l.addWidget(self.list_models, 1)
        self.tabs.addTab(tab, "Modeller")

    def on_model_double_clicked(self, item):
        self.on_model_selected(item)
        self.load_selected_model()

    def init_tab_config(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tab = QWidget()
        l = QVBoxLayout(tab)
        l.setSpacing(10)

        self.lbl_model_meta_summary = QLabel()
        self.lbl_model_meta_summary.setWordWrap(True)
        self.lbl_model_meta_summary.setStyleSheet("background: #1a1e2d; border: 1px solid #292e42; border-left: 3px solid #bb9af7; color: #7dcfff; padding: 10px; border-radius: 8px; font-size: 12px;")
        l.addWidget(self.lbl_model_meta_summary)

        h_quick_actions = QHBoxLayout()
        self.btn_inspect_meta = QPushButton("🔍 GGUF Metadata & Şablon Müfettişi")
        self.btn_inspect_meta.setStyleSheet("background: #1f2335; border: 1px solid #3b4261; color: #7dcfff; font-weight: bold; border-radius: 6px; padding: 7px;")
        self.btn_inspect_meta.clicked.connect(self.open_metadata_inspector)

        self.btn_autotune = QPushButton("⚡ Donanıma Göre Otomatik Ayarla (Auto-Tune)")
        self.btn_autotune.setStyleSheet("background: #1f2335; border: 1px solid #3b4261; color: #9ece6a; font-weight: bold; border-radius: 6px; padding: 7px;")
        self.btn_autotune.clicked.connect(self.autotune_for_hardware)
        h_quick_actions.addWidget(self.btn_inspect_meta, 1)
        h_quick_actions.addWidget(self.btn_autotune, 1)
        l.addLayout(h_quick_actions)

        mem_est_frame = QFrame()
        mem_est_frame.setStyleSheet("background: #1a1e2d; border: 1px solid #292e42; border-left: 3px solid #e0af68; border-radius: 8px; padding: 8px;")
        v_est = QVBoxLayout(mem_est_frame)
        v_est.setContentsMargins(6, 4, 6, 4)
        self.lbl_mem_estimate = QLabel(self.t("mem_est_initial"))
        self.lbl_mem_estimate.setWordWrap(True)
        self.lbl_mem_estimate.setStyleSheet("font-size: 12px; color: #e0af68;")
        self.bar_mem_estimate = QProgressBar()
        self.bar_mem_estimate.setRange(0, 100)
        self.bar_mem_estimate.setValue(0)
        self.bar_mem_estimate.setFixedHeight(10)
        v_est.addWidget(self.lbl_mem_estimate)
        v_est.addWidget(self.bar_mem_estimate)
        l.addWidget(mem_est_frame)

        self.grp_ctx = QGroupBox()
        v_ctx = QVBoxLayout(self.grp_ctx)
        h_ctx_top = QHBoxLayout()
        self.lbl_ctx_title = QLabel()
        self.spin_ctx = QSpinBox()
        self.spin_ctx.setRange(512, 1048576)
        self.spin_ctx.setSingleStep(1024)
        self.spin_ctx.setValue(8192)
        h_ctx_top.addWidget(self.lbl_ctx_title)
        h_ctx_top.addStretch()
        h_ctx_top.addWidget(self.spin_ctx)
        v_ctx.addLayout(h_ctx_top)

        self.slider_ctx = QSlider(Qt.Orientation.Horizontal)
        self.slider_ctx.setRange(512, 131072)
        self.slider_ctx.setValue(8192)
        self.slider_ctx.valueChanged.connect(self.spin_ctx.setValue)
        self.spin_ctx.valueChanged.connect(self.slider_ctx.setValue)
        v_ctx.addWidget(self.slider_ctx)

        h_ngl_top = QHBoxLayout()
        self.lbl_ngl_title = QLabel()
        self.spin_ngl = QSpinBox()
        self.spin_ngl.setRange(0, 256)
        self.spin_ngl.setValue(33)
        h_ngl_top.addWidget(self.lbl_ngl_title)
        h_ngl_top.addStretch()
        h_ngl_top.addWidget(self.spin_ngl)
        v_ctx.addLayout(h_ngl_top)

        self.slider_ngl = QSlider(Qt.Orientation.Horizontal)
        self.slider_ngl.setRange(0, 128)
        self.slider_ngl.setValue(33)
        self.slider_ngl.valueChanged.connect(self.spin_ngl.setValue)
        self.spin_ngl.valueChanged.connect(self.slider_ngl.setValue)
        v_ctx.addWidget(self.slider_ngl)
        l.addWidget(self.grp_ctx)

        self.grp_kv = QGroupBox()
        grid_kv = QGridLayout(self.grp_kv)
        grid_kv.addWidget(QLabel("K Cache (-ctk):"), 0, 0)
        self.cb_cache_k = QComboBox()
        self.cb_cache_k.addItems(["f16", "bf16", "q8_0", "q5_1", "q5_0", "q4_1", "q4_0", "iq4_nl"])
        grid_kv.addWidget(self.cb_cache_k, 0, 1)

        grid_kv.addWidget(QLabel("V Cache (-ctv):"), 0, 2)
        self.cb_cache_v = QComboBox()
        self.cb_cache_v.addItems(["f16", "bf16", "q8_0", "q5_1", "q5_0", "q4_1", "q4_0", "iq4_nl"])
        grid_kv.addWidget(self.cb_cache_v, 0, 3)

        self.chk_fa = QCheckBox("Flash Attention (-fa)")
        self.chk_fa.setChecked(True)
        self.chk_offload_kv = QCheckBox()
        self.chk_offload_kv.setChecked(True)
        grid_kv.addWidget(self.chk_fa, 1, 0, 1, 2)
        grid_kv.addWidget(self.chk_offload_kv, 1, 2, 1, 2)

        self.chk_mmap = QCheckBox()
        self.chk_mmap.setChecked(True)
        self.chk_mlock = QCheckBox()
        grid_kv.addWidget(self.chk_mmap, 2, 0, 1, 2)
        grid_kv.addWidget(self.chk_mlock, 2, 2, 1, 2)

        self.chk_prompt_cache = QCheckBox("⚡ Prompt Caching (Anlık Kodlama / Snapshot)")
        self.chk_prompt_cache.setChecked(True)
        self.chk_prompt_cache.setToolTip("Cursor/Continue gibi araçlarda sistem promptunu ve kod bağlamını önbelleğe alarak ilk token gecikmesini sıfırlar.")
        grid_kv.addWidget(self.chk_prompt_cache, 3, 0, 1, 4)
        l.addWidget(self.grp_kv)

        self.grp_batch = QGroupBox()
        grid_b = QGridLayout(self.grp_batch)
        grid_b.addWidget(QLabel("CPU Threads (-t):"), 0, 0)
        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, 128)
        self.spin_threads.setValue(max(1, (os.cpu_count() or 8) // 2))
        grid_b.addWidget(self.spin_threads, 0, 1)

        grid_b.addWidget(QLabel("Batch Threads (-tb):"), 0, 2)
        self.spin_threads_batch = QSpinBox()
        self.spin_threads_batch.setRange(1, 128)
        self.spin_threads_batch.setValue(os.cpu_count() or 8)
        grid_b.addWidget(self.spin_threads_batch, 0, 3)

        grid_b.addWidget(QLabel("Eval Batch (-b):"), 1, 0)
        self.spin_batch = QSpinBox()
        self.spin_batch.setRange(32, 16384)
        self.spin_batch.setSingleStep(256)
        self.spin_batch.setValue(2048)
        grid_b.addWidget(self.spin_batch, 1, 1)

        grid_b.addWidget(QLabel("Micro Batch (-ub):"), 1, 2)
        self.spin_ubatch = QSpinBox()
        self.spin_ubatch.setRange(32, 8192)
        self.spin_ubatch.setSingleStep(128)
        self.spin_ubatch.setValue(512)
        grid_b.addWidget(self.spin_ubatch, 1, 3)

        self.lbl_parallel = QLabel()
        grid_b.addWidget(self.lbl_parallel, 2, 0)
        self.spin_parallel = QSpinBox()
        self.spin_parallel.setRange(1, 32)
        self.spin_parallel.setValue(1)
        grid_b.addWidget(self.spin_parallel, 2, 1)

        self.chk_cont_batch = QCheckBox("Continuous Batching (-cb)")
        self.chk_cont_batch.setChecked(True)
        grid_b.addWidget(self.chk_cont_batch, 2, 2, 1, 2)

        grid_b.addWidget(QLabel("RoPE Freq Base:"), 3, 0)
        self.spin_rope_base = QDoubleSpinBox()
        self.spin_rope_base.setRange(0.0, 100000000.0)
        self.spin_rope_base.setDecimals(1)
        self.spin_rope_base.setValue(10000.0)
        grid_b.addWidget(self.spin_rope_base, 3, 1)

        grid_b.addWidget(QLabel("RoPE Scale:"), 3, 2)
        self.spin_rope_scale = QDoubleSpinBox()
        self.spin_rope_scale.setRange(0.0, 128.0)
        self.spin_rope_scale.setDecimals(2)
        self.spin_rope_scale.setValue(1.0)
        grid_b.addWidget(self.spin_rope_scale, 3, 3)
        l.addWidget(self.grp_batch)

        self.grp_spec = QGroupBox()
        v_spec = QVBoxLayout(self.grp_spec)
        h_effort = QHBoxLayout()
        self.lbl_effort = QLabel()
        self.cb_thinking_effort = QComboBox()
        eff_list = self.t('eff_items')
        if isinstance(eff_list, list):
            self.cb_thinking_effort.addItems([str(x) for x in eff_list])
        else:
            self.cb_thinking_effort.addItems(['Kapalı', 'Düşük (Low)', 'Orta (Medium)', 'Yüksek (High)', 'Özel Bütçe'])
        self.cb_thinking_effort.setEnabled(False)
        self.cb_thinking_effort.currentIndexChanged.connect(lambda idx: self.spin_thinking_tokens.setEnabled(idx == 4))
        h_effort.addWidget(self.lbl_effort)
        h_effort.addWidget(self.cb_thinking_effort)

        self.lbl_custom_budget = QLabel()
        self.spin_thinking_tokens = QSpinBox()
        self.spin_thinking_tokens.setRange(0, 65536)
        self.spin_thinking_tokens.setSingleStep(512)
        self.spin_thinking_tokens.setEnabled(False)
        h_effort.addWidget(self.lbl_custom_budget)
        h_effort.addWidget(self.spin_thinking_tokens)
        v_spec.addLayout(h_effort)

        self.chk_mtp = QCheckBox()
        self.chk_mtp.setEnabled(True)
        v_spec.addWidget(self.chk_mtp)

        h_draft = QHBoxLayout()
        self.chk_enable_draft = QCheckBox()
        self.btn_draft_pick = QPushButton()
        self.btn_draft_pick.setEnabled(False)
        self.btn_draft_pick.clicked.connect(self.choose_draft_model)
        self.lbl_draft_file = QLabel("Yok")
        self.spin_draft_max = QSpinBox()
        self.spin_draft_max.setRange(1, 32)
        self.spin_draft_max.setValue(4)
        self.spin_draft_max.setEnabled(False)
        h_draft.addWidget(self.chk_enable_draft)
        h_draft.addWidget(self.btn_draft_pick)
        h_draft.addWidget(self.lbl_draft_file)
        h_draft.addStretch()
        h_draft.addWidget(QLabel("Draft Max:"))
        h_draft.addWidget(self.spin_draft_max)
        v_spec.addLayout(h_draft)

        self.chk_enable_draft.toggled.connect(lambda c: (self.btn_draft_pick.setEnabled(c), self.spin_draft_max.setEnabled(c)))
        l.addWidget(self.grp_spec)

        self.grp_samp = QGroupBox()
        grid_s = QGridLayout(self.grp_samp)
        self.lbl_temp_title = QLabel()
        grid_s.addWidget(self.lbl_temp_title, 0, 0)
        self.spin_temp = QDoubleSpinBox()
        self.spin_temp.setRange(0.0, 3.0)
        self.spin_temp.setSingleStep(0.05)
        self.spin_temp.setValue(0.70)
        grid_s.addWidget(self.spin_temp, 0, 1)

        grid_s.addWidget(QLabel("Top-K:"), 0, 2)
        self.spin_topk = QSpinBox()
        self.spin_topk.setRange(0, 500)
        self.spin_topk.setValue(40)
        grid_s.addWidget(self.spin_topk, 0, 3)

        grid_s.addWidget(QLabel("Top-P:"), 1, 0)
        self.spin_topp = QDoubleSpinBox()
        self.spin_topp.setRange(0.0, 1.0)
        self.spin_topp.setSingleStep(0.05)
        self.spin_topp.setValue(0.90)
        grid_s.addWidget(self.spin_topp, 1, 1)

        grid_s.addWidget(QLabel("Min-P:"), 1, 2)
        self.spin_minp = QDoubleSpinBox()
        self.spin_minp.setRange(0.0, 1.0)
        self.spin_minp.setSingleStep(0.01)
        self.spin_minp.setValue(0.05)
        grid_s.addWidget(self.spin_minp, 1, 3)

        grid_s.addWidget(QLabel("Repeat Penalty:"), 2, 0)
        self.spin_rep_pen = QDoubleSpinBox()
        self.spin_rep_pen.setRange(1.0, 2.5)
        self.spin_rep_pen.setSingleStep(0.05)
        self.spin_rep_pen.setValue(1.10)
        grid_s.addWidget(self.spin_rep_pen, 2, 1)

        grid_s.addWidget(QLabel("Repeat Last N:"), 2, 2)
        self.spin_rep_n = QSpinBox()
        self.spin_rep_n.setRange(-1, 2048)
        self.spin_rep_n.setValue(64)
        grid_s.addWidget(self.spin_rep_n, 2, 3)

        grid_s.addWidget(QLabel("Presence Pen:"), 3, 0)
        self.spin_pres_pen = QDoubleSpinBox()
        self.spin_pres_pen.setRange(-2.0, 2.0)
        self.spin_pres_pen.setSingleStep(0.1)
        self.spin_pres_pen.setValue(0.0)
        grid_s.addWidget(self.spin_pres_pen, 3, 1)

        grid_s.addWidget(QLabel("Frequency Pen:"), 3, 2)
        self.spin_freq_pen = QDoubleSpinBox()
        self.spin_freq_pen.setRange(-2.0, 2.0)
        self.spin_freq_pen.setSingleStep(0.1)
        self.spin_freq_pen.setValue(0.0)
        grid_s.addWidget(self.spin_freq_pen, 3, 3)

        grid_s.addWidget(QLabel("Mirostat:"), 4, 0)
        self.cb_mirostat = QComboBox()
        self.cb_mirostat.addItems(["0 (Off)", "1 (v1)", "2 (v2)"])
        grid_s.addWidget(self.cb_mirostat, 4, 1)

        self.lbl_seed_title = QLabel()
        grid_s.addWidget(self.lbl_seed_title, 4, 2)
        self.spin_seed = QSpinBox()
        self.spin_seed.setRange(-1, 999999999)
        self.spin_seed.setValue(-1)
        grid_s.addWidget(self.spin_seed, 4, 3)
        l.addWidget(self.grp_samp)

        self.grp_adv_samp = QGroupBox("6. Gelişmiş Samplers (DRY, XTC, Dynamic Temp, YaRN && MoE)")
        grid_as = QGridLayout(self.grp_adv_samp)

        grid_as.addWidget(QLabel("DRY Multiplier:"), 0, 0)
        self.spin_dry_mult = QDoubleSpinBox()
        self.spin_dry_mult.setRange(0.0, 5.0)
        self.spin_dry_mult.setSingleStep(0.1)
        self.spin_dry_mult.setValue(0.0)
        grid_as.addWidget(self.spin_dry_mult, 0, 1)

        grid_as.addWidget(QLabel("DRY Base:"), 0, 2)
        self.spin_dry_base = QDoubleSpinBox()
        self.spin_dry_base.setRange(1.0, 4.0)
        self.spin_dry_base.setSingleStep(0.25)
        self.spin_dry_base.setValue(1.75)
        grid_as.addWidget(self.spin_dry_base, 0, 3)

        grid_as.addWidget(QLabel("XTC Probability:"), 1, 0)
        self.spin_xtc_prob = QDoubleSpinBox()
        self.spin_xtc_prob.setRange(0.0, 1.0)
        self.spin_xtc_prob.setSingleStep(0.05)
        self.spin_xtc_prob.setValue(0.0)
        grid_as.addWidget(self.spin_xtc_prob, 1, 1)

        grid_as.addWidget(QLabel("XTC Threshold:"), 1, 2)
        self.spin_xtc_thresh = QDoubleSpinBox()
        self.spin_xtc_thresh.setRange(0.0, 1.0)
        self.spin_xtc_thresh.setSingleStep(0.05)
        self.spin_xtc_thresh.setValue(0.10)
        grid_as.addWidget(self.spin_xtc_thresh, 1, 3)

        grid_as.addWidget(QLabel("Dynatemp Range:"), 2, 0)
        self.spin_dynatemp = QDoubleSpinBox()
        self.spin_dynatemp.setRange(0.0, 2.0)
        self.spin_dynatemp.setSingleStep(0.05)
        self.spin_dynatemp.setValue(0.0)
        grid_as.addWidget(self.spin_dynatemp, 2, 1)

        grid_as.addWidget(QLabel("Typical-P:"), 2, 2)
        self.spin_typical = QDoubleSpinBox()
        self.spin_typical.setRange(0.0, 1.0)
        self.spin_typical.setSingleStep(0.05)
        self.spin_typical.setValue(1.0)
        grid_as.addWidget(self.spin_typical, 2, 3)

        grid_as.addWidget(QLabel("RoPE Scaling:"), 3, 0)
        self.cb_rope_scaling = QComboBox()
        self.cb_rope_scaling.addItems(["Auto (Varsayılan)", "none", "linear", "yarn"])
        self.cb_rope_scaling.currentIndexChanged.connect(self.on_rope_scaling_changed)
        grid_as.addWidget(self.cb_rope_scaling, 3, 1)

        grid_as.addWidget(QLabel("YaRN Ext Factor:"), 3, 2)
        self.spin_yarn_ext = QDoubleSpinBox()
        self.spin_yarn_ext.setRange(-1.0, 16.0)
        self.spin_yarn_ext.setSingleStep(0.5)
        self.spin_yarn_ext.setValue(-1.0)
        grid_as.addWidget(self.spin_yarn_ext, 3, 3)
        l.addWidget(self.grp_adv_samp)

        self.grp_cli = QGroupBox("7. Chat Template Override && Ekstra CLI Parametreleri")
        v_cli = QVBoxLayout(self.grp_cli)

        h_tpl = QHBoxLayout()
        h_tpl.addWidget(QLabel("Chat Template Şablonu:"))
        self.cb_chat_template = QComboBox()
        self.cb_chat_template.addItems([
            "Otomatik (Modelin Gömülü Jinja Şablonu)",
            "chatml", "llama3", "deepseek", "deepseek3", "qwen2", "gemma", "mistral-v3", "command-r"
        ])
        h_tpl.addWidget(self.cb_chat_template, 1)
        v_cli.addLayout(h_tpl)

        h_custom_flags = QHBoxLayout()
        h_custom_flags.addWidget(QLabel("Ekstra Özel Argümanlar:"))
        self.input_custom_flags = QLineEdit()
        self.input_custom_flags.setPlaceholderText("Örn: --override-kv llama.expert_used_count=int:4 --no-context-shift")
        h_custom_flags.addWidget(self.input_custom_flags, 1)
        v_cli.addLayout(h_custom_flags)
        l.addWidget(self.grp_cli)

        self.spin_ctx.valueChanged.connect(self.recalculate_memory_estimate)
        self.spin_ngl.valueChanged.connect(self.recalculate_memory_estimate)
        self.cb_cache_k.currentIndexChanged.connect(self.recalculate_memory_estimate)
        self.cb_cache_v.currentIndexChanged.connect(self.recalculate_memory_estimate)

        # Fare Tekerleği Koruma Filtresi
        self._wheel_filter = NoWheelEventFilter(self)
        wheel_widgets = [
            self.spin_ctx, self.spin_ngl, self.spin_threads, self.spin_threads_batch,
            self.spin_batch, self.spin_ubatch, self.spin_parallel, self.spin_rope_base,
            self.spin_rope_scale, self.spin_temp, self.spin_topk, self.spin_topp,
            self.spin_minp, self.spin_rep_pen, self.spin_rep_n, self.spin_pres_pen,
            self.spin_freq_pen, self.spin_seed, self.spin_dry_mult, self.spin_dry_base,
            self.spin_xtc_prob, self.spin_xtc_thresh, self.spin_dynatemp, self.spin_typical,
            self.spin_yarn_ext, self.cb_cache_k, self.cb_cache_v, self.cb_rope_scaling,
            self.cb_chat_template, self.cb_mirostat
        ]
        for w in wheel_widgets:
            if w:
                w.installEventFilter(self._wheel_filter)

        # Ayar değiştiğinde otomatik kaydet
        auto_save = lambda *args: self.save_current_model_custom_config()
        self.spin_ctx.valueChanged.connect(auto_save)
        self.spin_ngl.valueChanged.connect(auto_save)
        self.spin_temp.valueChanged.connect(auto_save)
        self.spin_topp.valueChanged.connect(auto_save)
        self.spin_minp.valueChanged.connect(auto_save)
        self.spin_topk.valueChanged.connect(auto_save)
        self.spin_threads.valueChanged.connect(auto_save)
        self.spin_batch.valueChanged.connect(auto_save)
        self.spin_ubatch.valueChanged.connect(auto_save)
        self.cb_cache_k.currentIndexChanged.connect(auto_save)
        self.cb_cache_v.currentIndexChanged.connect(auto_save)
        self.chk_fa.toggled.connect(auto_save)
        self.chk_mmap.toggled.connect(auto_save)
        self.chk_mlock.toggled.connect(auto_save)
        if hasattr(self, "chk_prompt_cache"):
            self.chk_prompt_cache.toggled.connect(auto_save)


        l.addStretch()
        scroll.setWidget(tab)
        self.tabs.addTab(scroll, "Model Ayarları")

    def init_tab_hardware(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tab = QWidget()
        l = QVBoxLayout(tab)
        l.setSpacing(10)

        engine_bin = os.path.join(USER_ENGINES_DIR, "llama-server")
        if not os.path.exists(engine_bin):
            engine_bin = os.path.join(BASE_DIR, "engines", "llama-server")
        self.hw_info = get_system_hardware(engine_bin)

        cpu_card = QFrame()
        cpu_card.setStyleSheet("background: #1f2335; border: 1px solid #292e42; border-radius: 8px; padding: 8px;")
        v_cpu = QVBoxLayout(cpu_card)
        self.lbl_hw_cpu_ok = QLabel()
        lbl_c2 = QLabel(f"{self.hw_info['cpu_name']}")
        lbl_c2.setWordWrap(True)
        badges = " ".join([f"<span style='background:#292e42; padding:2px 6px; border-radius:4px; font-size:11px;'>{b}</span>" for b in [self.hw_info['cpu_arch']] + self.hw_info['cpu_flags']])
        self.lbl_hw_isa = QLabel(badges)
        self.lbl_hw_isa.setWordWrap(True)
        v_cpu.addWidget(self.lbl_hw_cpu_ok)
        v_cpu.addWidget(lbl_c2)
        v_cpu.addWidget(self.lbl_hw_isa)
        l.addWidget(cpu_card)

        mem_card = QFrame()
        mem_card.setStyleSheet("background: #1f2335; border: 1px solid #292e42; border-radius: 8px; padding: 8px;")
        h_mem = QHBoxLayout(mem_card)
        self.lbl_hw_ram = QLabel()
        self.lbl_hw_vram = QLabel()
        h_mem.addWidget(self.lbl_hw_ram)
        h_mem.addWidget(self.lbl_hw_vram)
        l.addWidget(mem_card)

        self.grp_gpus = QGroupBox()
        v_gpus = QVBoxLayout(self.grp_gpus)

        strat_box = QHBoxLayout()
        self.lbl_hw_split = QLabel()
        self.cb_split_mode = QComboBox()
        self.cb_split_mode.addItem("Layer Split", "layer")
        self.cb_split_mode.addItem("Row Split", "row")
        self.cb_split_mode.addItem("Single GPU", "none")
        strat_box.addWidget(self.lbl_hw_split)
        strat_box.addWidget(self.cb_split_mode)
        v_gpus.addLayout(strat_box)

        # Çoklu GPU Hibrit Katman / Bellek Oran Kaydırıcısı (Tensor-Split)
        self.frame_gpu_ratio = QFrame()
        self.frame_gpu_ratio.setStyleSheet("background: #1a1b26; border: 1px solid #3b4261; border-radius: 6px; padding: 6px;")
        v_ratio = QVBoxLayout(self.frame_gpu_ratio)
        v_ratio.setContentsMargins(6, 4, 6, 4)

        self.lbl_gpu_ratio_title = QLabel("⚖️ <b>Çoklu GPU Yük / VRAM Oranı:</b> GPU 0 (%50) ⟷ GPU 1 (%50)")
        self.lbl_gpu_ratio_title.setStyleSheet("color: #7dcfff; font-size: 11px;")
        v_ratio.addWidget(self.lbl_gpu_ratio_title)

        self.slider_gpu_ratio = QSlider(Qt.Orientation.Horizontal)
        self.slider_gpu_ratio.setRange(5, 95)
        saved_ratio = self.cfg.get("gpu_split_ratio", 50)
        self.slider_gpu_ratio.setValue(saved_ratio)
        self.slider_gpu_ratio.valueChanged.connect(self._on_gpu_ratio_changed)
        v_ratio.addWidget(self.slider_gpu_ratio)
        v_gpus.addWidget(self.frame_gpu_ratio)

        # Eğer sistemde birden az aktif GPU varsa kaydırıcıyı gizle
        if len(self.hw_info.get("gpus", [])) < 2:
            self.frame_gpu_ratio.hide()

        self.gpu_vram_widgets = {}
        saved_gpu_states = self.cfg.get("enabled_gpus", {})

        for g in self.hw_info["gpus"]:
            dev_id = str(g["id"])
            card_row = QFrame()
            card_row.setStyleSheet("""
                QFrame {
                    background: #1f2335;
                    border: 1px solid #292e42;
                    border-radius: 8px;
                    padding: 6px;
                }
            """)
            v_card = QVBoxLayout(card_row)
            v_card.setContentsMargins(10, 8, 10, 8)
            v_card.setSpacing(6)

            # Üst Satır: Kart Adı + ID Rozeti + ON/OFF Butonu
            h_top = QHBoxLayout()
            lbl_title = QLabel(
                f"<b>{g['name']}</b> "
                f"<span style='background:#24283b; color:#7aa2f7; padding:2px 6px; border-radius:4px; font-size:11px; border:1px solid #3b4261;'>{g['backend']} (ID: {g['id']})</span>"
            )
            lbl_title.setWordWrap(True)

            btn_toggle = QPushButton()
            btn_toggle.setCheckable(True)
            btn_toggle.setFixedSize(85, 28)
            is_on = saved_gpu_states.get(dev_id, True)
            btn_toggle.setChecked(is_on)
            self._update_gpu_btn_style(btn_toggle, is_on)
            btn_toggle.toggled.connect(lambda checked, b=btn_toggle, d=dev_id: self._on_gpu_toggled(b, d, checked))
            self.gpu_toggles[g["id"]] = btn_toggle

            h_top.addWidget(lbl_title, 1)
            h_top.addWidget(btn_toggle)
            v_card.addLayout(h_top)

            # Alt Kısım: Canlı VRAM Kullanım Sayacı ve İlerleme Çubuğu
            h_vram_txt = QHBoxLayout()
            lbl_vram_stat = QLabel(f"📊 VRAM Kullanımı: <b>0.00 / {g['vram_gb']:.2f} GB</b> (%0.0)")
            lbl_vram_stat.setStyleSheet("color: #73daca; font-size: 11px;")
            h_vram_txt.addWidget(lbl_vram_stat)
            h_vram_txt.addStretch()
            v_card.addLayout(h_vram_txt)

            bar_vram = QProgressBar()
            bar_vram.setRange(0, 100)
            bar_vram.setValue(0)
            bar_vram.setFixedHeight(8)
            bar_vram.setTextVisible(False)
            bar_vram.setStyleSheet("""
                QProgressBar { background: #16161e; border-radius: 4px; border: 1px solid #292e42; }
                QProgressBar::chunk { background: #7aa2f7; border-radius: 3px; }
            """)
            v_card.addWidget(bar_vram)

            self.gpu_vram_widgets[g["id"]] = {
                "bar": bar_vram,
                "label": lbl_vram_stat,
                "total_gb": max(0.5, g["vram_gb"]),
                "drm_card": g.get("drm_card", g["id"]),
                "is_igpu": g.get("is_igpu", False)
            }

            v_gpus.addWidget(card_row)

        l.addWidget(self.grp_gpus)

        # Gelişmiş Canlı Sistem Kaynak Paneli (Dashboard)
        self.grp_mon = QGroupBox()
        grid_mon = QGridLayout(self.grp_mon)
        grid_mon.setContentsMargins(10, 10, 10, 10)
        grid_mon.setSpacing(8)

        # RAM Monitörü
        self.lbl_mon_ram = QLabel(f"💾 Sistem RAM: <b>0.00 / {self.hw_info['ram_gb']} GB</b> (%0)")
        self.lbl_mon_ram.setStyleSheet("font-size: 11px; color: #c0caf5;")
        self.bar_mon_ram = QProgressBar()
        self.bar_mon_ram.setRange(0, 100)
        self.bar_mon_ram.setFixedHeight(8)
        self.bar_mon_ram.setTextVisible(False)
        self.bar_mon_ram.setStyleSheet("QProgressBar { background: #16161e; border-radius: 4px; } QProgressBar::chunk { background: #7aa2f7; border-radius: 3px; }")

        grid_mon.addWidget(self.lbl_mon_ram, 0, 0)
        grid_mon.addWidget(self.bar_mon_ram, 1, 0)

        # CPU Monitörü
        self.lbl_mon_cpu = QLabel("⚡ İşlemci (CPU) Yükü: <b>%0.0</b>")
        self.lbl_mon_cpu.setStyleSheet("font-size: 11px; color: #c0caf5;")
        self.bar_mon_cpu = QProgressBar()
        self.bar_mon_cpu.setRange(0, 100)
        self.bar_mon_cpu.setFixedHeight(8)
        self.bar_mon_cpu.setTextVisible(False)
        self.bar_mon_cpu.setStyleSheet("QProgressBar { background: #16161e; border-radius: 4px; } QProgressBar::chunk { background: #bb9af7; border-radius: 3px; }")

        grid_mon.addWidget(self.lbl_mon_cpu, 0, 1)
        grid_mon.addWidget(self.bar_mon_cpu, 1, 1)

        l.addWidget(self.grp_mon)

        l.addStretch()
        scroll.setWidget(tab)
        self.tabs.addTab(scroll, "Donanım")

    def _update_gpu_btn_style(self, btn, is_on):
        if is_on:
            btn.setText("ON")
            btn.setStyleSheet("background-color: #7aa2f7; color: #15161e; font-weight: bold; border-radius: 14px;")
        else:
            btn.setText("OFF")
            btn.setStyleSheet("background-color: #414868; color: #a9b1d6; font-weight: bold; border-radius: 14px;")

    def _on_gpu_ratio_changed(self, val):
        r0 = val
        r1 = 100 - val
        gpus = self.hw_info.get("gpus", [])
        g0_name = gpus[0]["name"] if len(gpus) > 0 else "GPU 0"
        g1_name = gpus[1]["name"] if len(gpus) > 1 else "GPU 1"
        self.lbl_gpu_ratio_title.setText(
            f"⚖️ <b>Çoklu GPU Yük / VRAM Oranı:</b> {g0_name[:14]} (%{r0}) ⟷ {g1_name[:14]} (%{r1})"
        )
        self.cfg["gpu_split_ratio"] = val
        save_json(CONFIG_FILE, self.cfg)

    def _on_gpu_toggled(self, btn, dev_id, checked):
        self._update_gpu_btn_style(btn, checked)
        if "enabled_gpus" not in self.cfg:
            self.cfg["enabled_gpus"] = {}
        self.cfg["enabled_gpus"][dev_id] = checked
        save_json(CONFIG_FILE, self.cfg)

    def update_resource_monitor(self):
        if not self.isVisible():
            return

        # 1. RAM & CPU İzleme
        mem = psutil.virtual_memory()
        used_gb = round(mem.used / (1024**3), 2)
        total_ram = self.hw_info.get("ram_gb", 32.0)
        ram_pct = min(100, int((used_gb / total_ram) * 100)) if total_ram > 0 else 0
        cpu_pct = psutil.cpu_percent(interval=None)

        if hasattr(self, "lbl_mon_ram"):
            self.lbl_mon_ram.setText(f"💾 Sistem RAM: <b>{used_gb:.2f} / {total_ram:.2f} GB</b> (%{ram_pct})")
        if hasattr(self, "bar_mon_ram"):
            self.bar_mon_ram.setValue(ram_pct)

        if hasattr(self, "lbl_mon_cpu"):
            self.lbl_mon_cpu.setText(f"⚡ İşlemci (CPU) Yükü: <b>%{cpu_pct:.1f}</b>")
        if hasattr(self, "bar_mon_cpu"):
            self.bar_mon_cpu.setValue(int(cpu_pct))

        # 2. Kart Bazlı Canlı VRAM Barlarını Güncelle
        if hasattr(self, "gpu_vram_widgets"):
            for gid, w_dict in self.gpu_vram_widgets.items():
                c_idx = w_dict.get("drm_card", gid)
                is_ig = w_dict.get("is_igpu", None)
                live_used = read_drm_vram_used_gb(c_idx, is_igpu=is_ig)
                tot = w_dict["total_gb"]
                pct_val = min(100.0, (live_used / tot) * 100.0) if tot > 0 else 0.0

                w_dict["label"].setText(
                    f"📊 VRAM Kullanımı: <b>{live_used:.2f} / {tot:.2f} GB</b> (%{pct_val:.1f})"
                )
                bar = w_dict["bar"]
                bar.setValue(int(pct_val))

                # Doluluğa göre dinamik renk
                if pct_val >= 90:
                    bar_color = "#f7768e" # Kırmızı (Kritik)
                elif pct_val >= 75:
                    bar_color = "#e0af68" # Turuncu (Yoğun)
                else:
                    bar_color = "#7aa2f7" # Mavi (Normal)

                bar.setStyleSheet(f"""
                    QProgressBar {{ background: #16161e; border-radius: 4px; border: 1px solid #292e42; }}
                    QProgressBar::chunk {{ background: {bar_color}; border-radius: 3px; }}
                """)

    def init_tab_server(self):
        tab = QWidget()
        l = QVBoxLayout(tab)
        l.setSpacing(8)

        self.grp_srv_mgmt = QGroupBox()
        h_srv = QHBoxLayout(self.grp_srv_mgmt)
        self.lbl_srv_state = QLabel()
        self.btn_srv_toggle = QPushButton()
        self.btn_srv_toggle.setObjectName("stopBtn")
        self.btn_srv_toggle.clicked.connect(self.toggle_server_service)
        h_srv.addWidget(self.lbl_srv_state)
        h_srv.addStretch()
        h_srv.addWidget(self.btn_srv_toggle)
        l.addWidget(self.grp_srv_mgmt)

        self.grp_srv_net = QGroupBox()
        v_net = QVBoxLayout(self.grp_srv_net)

        h_port = QHBoxLayout()
        self.lbl_port_title = QLabel()
        self.spin_port = QSpinBox()
        self.spin_port.setRange(1024, 65535)
        self.spin_port.setValue(int(self.cfg.get("port", 8080)))
        self.spin_port.valueChanged.connect(self.update_endpoint_display)
        h_port.addWidget(self.lbl_port_title)
        h_port.addWidget(self.spin_port)
        
        self.btn_copy_url = QPushButton()
        self.btn_copy_url.clicked.connect(self.copy_endpoint_url)
        h_port.addStretch()
        h_port.addWidget(self.btn_copy_url)
        v_net.addLayout(h_port)

        self.chk_lan = QCheckBox()
        self.chk_lan.setChecked(True)
        self.chk_lan.toggled.connect(self.update_endpoint_display)
        v_net.addWidget(self.chk_lan)

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            self.local_ip = s.getsockname()[0]
            s.close()
        except:
            self.local_ip = "127.0.0.1"

        self.lbl_ip = QLabel()
        self.lbl_ip.setWordWrap(True)
        self.lbl_ip.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl_ip.setStyleSheet("color: #73daca; font-size: 12px; padding: 8px; background: #1f2335; border-radius: 6px;")
        v_net.addWidget(self.lbl_ip)

        self.chk_cors = QCheckBox()
        self.chk_cors.setChecked(True)
        v_net.addWidget(self.chk_cors)

        self.chk_tools = QCheckBox()
        self.chk_tools.setChecked(True)
        v_net.addWidget(self.chk_tools)
        l.addWidget(self.grp_srv_net)

        self.grp_srv_logs = QGroupBox()
        v_log = QVBoxLayout(self.grp_srv_logs)
        v_log.setSpacing(6)

        # Log Hızlı Araç Çubuğu (Toolbar)
        h_log_tools = QHBoxLayout()
        h_log_tools.setSpacing(6)

        self.input_log_filter = QLineEdit()
        self.input_log_filter.setPlaceholderText("🔎 Loglarda ara / filtrele (örn: vulkan, error, slot, tokens)...")
        self.input_log_filter.setClearButtonEnabled(True)
        self.input_log_filter.setFixedHeight(28)
        self.input_log_filter.textChanged.connect(self.filter_server_logs)

        self.chk_log_autoscroll = QCheckBox("Otomatik Kaydır")
        self.chk_log_autoscroll.setChecked(True)
        self.chk_log_autoscroll.setStyleSheet("font-size: 11px; color: #a9b1d6;")

        btn_copy_style = """
            QPushButton {
                background: transparent;
                border: none;
                color: #a9b1d6;
                font-size: 15px;
                border-radius: 6px;
                padding: 2px;
            }
            QPushButton:hover {
                background: rgba(122, 162, 247, 0.15);
                color: #7dcfff;
            }
        """
        btn_clear_style = """
            QPushButton {
                background: transparent;
                border: none;
                color: #a9b1d6;
                font-size: 15px;
                border-radius: 6px;
                padding: 2px;
            }
            QPushButton:hover {
                background: rgba(247, 118, 142, 0.18);
                color: #f7768e;
            }
        """

        self.btn_copy_logs = QPushButton("📋")
        self.btn_copy_logs.setFixedSize(28, 28)
        self.btn_copy_logs.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy_logs.setToolTip("Tüm logları panoya kopyala")
        self.btn_copy_logs.setStyleSheet(btn_copy_style)
        self.btn_copy_logs.clicked.connect(self.copy_all_logs)

        self.btn_clear_logs = QPushButton("🧹")
        self.btn_clear_logs.setFixedSize(28, 28)
        self.btn_clear_logs.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_logs.setToolTip("Log ekranını temizle")
        self.btn_clear_logs.setStyleSheet(btn_clear_style)
        self.btn_clear_logs.clicked.connect(self.clear_server_logs)

        h_log_tools.addWidget(self.input_log_filter, 1)
        h_log_tools.addWidget(self.chk_log_autoscroll)
        h_log_tools.addWidget(self.btn_copy_logs)
        h_log_tools.addWidget(self.btn_clear_logs)
        v_log.addLayout(h_log_tools)

        self.txt_logs = QPlainTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setStyleSheet("""
            QPlainTextEdit {
                background: #13141c;
                color: #9ece6a;
                font-family: 'Ubuntu Mono', 'Courier New', monospace;
                font-size: 11px;
                border: 1px solid #292e42;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        v_log.addWidget(self.txt_logs, 1)
        l.addWidget(self.grp_srv_logs, 1)

        self.tabs.addTab(tab, "Sunucu")

    def copy_endpoint_url(self):
        port = getattr(self, 'upstream_port', self.spin_port.value() + 1)
        ip = self.local_ip if self.chk_lan.isChecked() else "127.0.0.1"
        url = f"http://{ip}:{port}/v1"
        QApplication.clipboard().setText(url)
        self.status_lbl.setText("📋 API URL Copied!")

    def update_endpoint_display(self):
        # Dış dünyaya açık Gateway portu doğrudan spin_port değeridir
        user_port = self.spin_port.value()
        self.upstream_port = user_port + 1
        self.cfg["port"] = user_port
        save_json(CONFIG_FILE, self.cfg)

        if hasattr(self, "poller"):
            self.poller.set_port(self.upstream_port)

        if self.chk_lan.isChecked():
            self.lbl_ip.setText(
                f"🌐 <b>LAN Endpoint:</b> http://{self.local_ip}:{user_port}/v1<br>"
                f"💻 <b>Localhost:</b> http://127.0.0.1:{user_port}/v1"
            )
        else:
            self.lbl_ip.setText(f"🔒 <b>Localhost Only:</b> http://127.0.0.1:{user_port}/v1")

    def toggle_server_service(self):
        if self.server_service_enabled:
            self.server_service_enabled = False
            if self.server_mgr.is_running():
                self.unload_current_model()
            self.lbl_srv_state.setText(self.t("srv_state_off"))
            self.btn_srv_toggle.setText(self.t("btn_srv_start"))
            self.set_status_badge("stopped", self.t("srv_stopped"))
            self.btn_load_model.setEnabled(False)
            tray_ref.setIcon(get_tray_icon("stopped"))
        else:
            self.server_service_enabled = True
            self.lbl_srv_state.setText(self.t("srv_state_on"))
            self.btn_srv_toggle.setText(self.t("btn_srv_stop"))
            self.status_lbl.setText(self.t("srv_wait_model"))
            self.status_lbl.setStyleSheet("color: #7dcfff; font-weight: bold;")
            self.btn_load_model.setEnabled(True)
            tray_ref.setIcon(get_tray_icon("ready"))

    def init_tab_hf(self):
        tab = QWidget()
        l = QVBoxLayout(tab)
        l.setSpacing(6)

        search_row = QHBoxLayout()
        self.input_hf = QLineEdit()
        self.input_hf.returnPressed.connect(lambda: self.fetch_hf_models(mode="search"))
        self.btn_hf_search = QPushButton()
        self.btn_hf_search.clicked.connect(lambda: self.fetch_hf_models(mode="search"))
        search_row.addWidget(self.input_hf, 1)
        search_row.addWidget(self.btn_hf_search)
        l.addLayout(search_row)

        filter_row = QHBoxLayout()
        self.btn_hf_trend = QPushButton()
        self.btn_hf_trend.clicked.connect(lambda: self.fetch_hf_models(mode="trending"))
        self.btn_hf_dl = QPushButton()
        self.btn_hf_dl.clicked.connect(lambda: self.fetch_hf_models(mode="downloads"))
        self.btn_hf_likes = QPushButton()
        self.btn_hf_likes.clicked.connect(lambda: self.fetch_hf_models(mode="likes"))
        self.btn_hf_new = QPushButton()
        self.btn_hf_new.clicked.connect(lambda: self.fetch_hf_models(mode="recent"))
        filter_row.addWidget(self.btn_hf_trend)
        filter_row.addWidget(self.btn_hf_dl)
        filter_row.addWidget(self.btn_hf_likes)
        filter_row.addWidget(self.btn_hf_new)
        l.addLayout(filter_row)

        self.lbl_hf_models = QLabel()
        l.addWidget(self.lbl_hf_models)

        self.list_hf_models = QListWidget()
        self.list_hf_models.setWordWrap(True)
        self.list_hf_models.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_hf_models.itemClicked.connect(self.on_hf_repo_clicked)
        l.addWidget(self.list_hf_models, 3)

        self.lbl_hf_files = QLabel()
        l.addWidget(self.lbl_hf_files)

        self.list_hf_files = QListWidget()
        self.list_hf_files.setWordWrap(True)
        self.list_hf_files.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        l.addWidget(self.list_hf_files, 2)

        self.tabs.addTab(tab, "Hugging Face")

    def fetch_hf_models(self, mode="trending"):
        query = self.input_hf.text().strip() if mode == "search" else ""
        self.list_hf_models.clear()
        self.list_hf_models.addItem("⏳ Hugging Face üzerinden modeller getiriliyor...")
        token = self.cfg.get("hf_token", "")
        self.hf_search_worker = HFSearchWorker(query=query, mode=mode, limit=25, token=token)
        self.hf_search_worker.results_ready.connect(self.on_hf_results_ready)
        self.hf_search_worker.error_occurred.connect(self.on_hf_error)
        self.hf_search_worker.start()

    def on_hf_results_ready(self, results):
        self.list_hf_models.clear()
        if not results:
            self.list_hf_models.addItem("Sonuç bulunamadı.")
            return

        for r in results:
            caps = r["caps"]
            badges = []
            if caps["thinking"]: badges.append("🧠 Düşünce")
            if caps["tools"]: badges.append("🔧 Araçlar")
            if caps["vision"]: badges.append("👁️ Görsel")
            if caps["audio"]: badges.append("🎙️ Ses")
            b_str = f"  [{' | '.join(badges)}]" if badges else ""

            txt = f"📦 {r['id']}\n↳ ⬇️ {r['downloads']:,}  |  ⭐ {r['likes']:,}{b_str}"
            item = QListWidgetItem(txt)
            item.setData(Qt.ItemDataRole.UserRole, r["id"])
            self.list_hf_models.addItem(item)

    def on_hf_error(self, err):
        self.list_hf_models.clear()
        self.list_hf_models.addItem(f"❌ Hata: {err}")

    def on_hf_repo_clicked(self, item):
        repo_id = item.data(Qt.ItemDataRole.UserRole)
        if not repo_id:
            return
        self.list_hf_files.clear()
        self.list_hf_files.addItem(f"⏳ {repo_id} içindeki GGUF dosyaları ve boyutları okunuyor...")
        token = self.cfg.get("hf_token", "")
        self.hf_files_worker = HFFilesWorker(repo_id=repo_id, token=token)
        self.hf_files_worker.files_ready.connect(self.on_hf_files_ready)
        self.hf_files_worker.error_occurred.connect(lambda e: self.list_hf_files.addItem(f"❌ {e}"))
        self.hf_files_worker.start()

    def on_hf_files_ready(self, repo_id, files):
        self.list_hf_files.clear()
        if not files:
            self.list_hf_files.addItem("Bu depoda doğrudan .gguf uzantılı dosya bulunamadı.")
            return

        for f in files:
            item = QListWidgetItem()
            row_w = QWidget()
            h = QHBoxLayout(row_w)
            h.setContentsMargins(6, 4, 6, 4)

            lbl = QLabel(
                f"<b>{f['filename']}</b><br>"
                f"<span style='color:#73daca; font-size:11px;'>Quant: <b>{f['quant']}</b>  •  Boyut: <b>{f['size_gb']} GB</b></span>"
            )
            lbl.setWordWrap(True)
            btn_dl = QPushButton("⬇️ İndir")
            btn_dl.setFixedSize(85, 28)
            btn_dl.setStyleSheet("background: #7aa2f7; color: #15161e; font-weight: bold;")
            btn_dl.clicked.connect(lambda _, file_info=f: self.start_hf_download(file_info))

            h.addWidget(lbl, 1)
            h.addWidget(btn_dl)
            item.setSizeHint(row_w.sizeHint())
            self.list_hf_files.addItem(item)
            self.list_hf_files.setItemWidget(item, row_w)

    def init_tab_downloads(self):
        tab = QWidget()
        l = QVBoxLayout(tab)
        self.lbl_dl_header = QLabel()
        l.addWidget(self.lbl_dl_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.dl_container = QWidget()
        self.dl_layout = QVBoxLayout(self.dl_container)
        self.dl_layout.setSpacing(8)
        self.lbl_dl_empty = QLabel()
        self.lbl_dl_empty.setStyleSheet("color: #565f89; padding: 15px;")
        self.dl_layout.addWidget(self.lbl_dl_empty)
        self.dl_layout.addStretch()
        scroll.setWidget(self.dl_container)
        l.addWidget(scroll, 1)
        self.tabs.addTab(tab, "İndirilenler")

    def start_hf_download(self, file_info):
        target_dir = self.cfg.get("last_folder", "")
        if not target_dir or not os.path.isdir(target_dir):
            target_dir = QFileDialog.getExistingDirectory(self, "İndirilecek Model Klasörünü Seç", os.path.expanduser("~"))
            if not target_dir:
                return
            self.cfg["last_folder"] = target_dir
            save_json(CONFIG_FILE, self.cfg)
            self.lbl_folder.setText(f".../{os.path.basename(target_dir)}")

        dest_path = os.path.join(target_dir, file_info["filename"])
        task_id = f"{file_info['repo_id']}/{file_info['filename']}"
        if task_id in self.active_downloads:
            self.tabs.setCurrentIndex(5)
            return

        self.lbl_dl_empty.hide()
        token = self.cfg.get("hf_token", "")
        worker = DownloadWorker(task_id=task_id, url=file_info["url"], dest_path=dest_path, token=token)
        widget = DownloadItemWidget(task_id, file_info["filename"], file_info["repo_id"], worker)
        self.dl_layout.insertWidget(0, widget)
        self.active_downloads[task_id] = (worker, widget)

        worker.progress.connect(self.on_dl_progress)
        worker.finished_dl.connect(self.on_dl_finished)
        worker.error.connect(self.on_dl_error)
        worker.start()

        self.tabs.setCurrentIndex(5)

    def on_dl_progress(self, task_id, pct, dl_mb, total_mb, speed_mb):
        if task_id in self.active_downloads:
            _, w = self.active_downloads[task_id]
            w.prog.setValue(pct)
            w.lbl_stats.setText(f"{dl_mb:.1f} / {total_mb:.1f} MB ({speed_mb:.1f} MB/s)")

    def on_dl_finished(self, task_id, dest_path):
        if task_id in self.active_downloads:
            _, w = self.active_downloads[task_id]
            w.prog.setValue(100)
            w.lbl_state.setText("✅ Tamamlandı! Model listesine eklendi.")
            w.lbl_state.setStyleSheet("color: #9ece6a; font-weight: bold;")
            w.btn_pause.setEnabled(False)
            w.btn_cancel.setEnabled(False)
        folder = self.cfg.get("last_folder", "")
        if folder and os.path.isdir(folder):
            self.load_from_sqlite_instant(folder)
        fn = os.path.basename(dest_path)
        self.notify_desktop(
            "Tray AI — İndirme Tamamlandı",
            f"'{fn}' başarıyla indirildi ve modellere eklendi. ✅",
            "info"
        )

    def on_dl_error(self, task_id, err_msg):
        if task_id in self.active_downloads:
            _, w = self.active_downloads[task_id]
            w.lbl_state.setText(f"❌ Hata: {err_msg}")
            w.lbl_state.setStyleSheet("color: #f7768e;")
        self.notify_desktop(
            "Tray AI — İndirme Başarısız",
            f"{task_id} indirilirken hata oluştu: {err_msg}",
            "error"
        )

    def apply_language(self):
        self.lbl_title.setText(f"⚡ <b>Tray AI</b> <span style='font-size:11px; color:#565f89;'>{self.t('drag_hint')}</span>")
        if not self.server_mgr.is_running():
            self.set_status_badge("waiting" if self.server_service_enabled else "stopped", self.t("srv_wait_model") if self.server_service_enabled else self.t("srv_stopped"))
            self.lbl_load_stage.setText(self.t("lbl_no_model"))
            self.btn_load_model.setText(self.t("btn_load"))
        else:
            self.btn_load_model.setText(self.t("btn_reload"))

        self.btn_unload_model.setText(self.t("btn_unload"))
        self.btn_drop_cache.setText(self.t("btn_drop_cache"))
        self.btn_abort_gen.setText(self.t("btn_abort"))

        self.tabs.setTabText(0, self.t("tab_models"))
        self.tabs.setTabText(1, self.t("tab_config"))
        self.tabs.setTabText(2, self.t("tab_hw"))
        self.tabs.setTabText(3, self.t("tab_server"))
        self.tabs.setTabText(4, self.t("tab_hf"))
        self.tabs.setTabText(5, self.t("tab_dl"))

        if hasattr(self, "btn_open_folder"):
            self.btn_open_folder.setText(self.t("btn_show_folder"))
        if hasattr(self, "btn_delete_model"):
            self.btn_delete_model.setText(self.t("btn_delete"))
        if hasattr(self, "input_model_search"):
            self.input_model_search.setPlaceholderText(self.t("search_model_placeholder"))
        if hasattr(self, "btn_inspect_meta"):
            self.btn_inspect_meta.setText(self.t("btn_inspect"))
        if hasattr(self, "btn_autotune"):
            self.btn_autotune.setText(self.t("btn_autotune"))
        if hasattr(self, "btn_check_eng_updates"):
            self.btn_check_eng_updates.setText(self.t("btn_check_eng_updates"))
        if hasattr(self, "chk_auto_update_eng"):
            self.chk_auto_update_eng.setText(self.t("chk_auto_update_eng"))

        # Filtre ve Sıralama ComboBox Dillerini Güncelle
        if hasattr(self, "cb_model_filter"):
            cur_f = self.cb_model_filter.currentIndex()
            self.cb_model_filter.blockSignals(True)
            self.cb_model_filter.clear()
            self.cb_model_filter.addItems([
                self.t("filter_all"), self.t("filter_mtp"), self.t("filter_yarn"),
                self.t("filter_thinking"), self.t("filter_tools"), self.t("filter_moe"),
                self.t("filter_vision")
            ])
            self.cb_model_filter.setCurrentIndex(cur_f if cur_f >= 0 else 0)
            self.cb_model_filter.blockSignals(False)

        if hasattr(self, "cb_model_sort"):
            cur_s = self.cb_model_sort.currentIndex()
            self.cb_model_sort.blockSignals(True)
            self.cb_model_sort.clear()
            self.cb_model_sort.addItems([
                self.t("sort_name"), self.t("sort_size_asc"),
                self.t("sort_size_desc"), self.t("sort_ctx")
            ])
            self.cb_model_sort.setCurrentIndex(cur_s if cur_s >= 0 else 0)
            self.cb_model_sort.blockSignals(False)

        self.btn_select_dir.setText(self.t("btn_pick_dir"))
        self.btn_rescan.setText(self.t("btn_rescan"))
        if not self.cfg.get("last_folder"):
            self.lbl_folder.setText(self.t("lbl_no_folder"))

        if not self.active_model_info:
            self.lbl_model_meta_summary.setText(self.t("lbl_no_meta"))
        self.grp_ctx.setTitle(self.t("grp_ctx"))
        self.lbl_ctx_title.setText(self.t("lbl_ctx"))
        self.lbl_ngl_title.setText(self.t("lbl_ngl"))
        self.grp_kv.setTitle(self.t("grp_kv"))
        self.chk_offload_kv.setText(self.t("chk_kv_gpu"))
        self.chk_mmap.setText(self.t("chk_mmap"))
        self.chk_mlock.setText(self.t("chk_mlock"))
        if hasattr(self, "chk_prompt_cache"): self.chk_prompt_cache.setText(self.t("chk_prompt_cache", "⚡ Prompt Caching (Anlık Kodlama / Snapshot)"))
        self.grp_batch.setTitle(self.t("grp_batch"))
        self.lbl_parallel.setText(self.t("lbl_parallel"))
        self.grp_spec.setTitle(self.t("grp_spec"))
        self.lbl_effort.setText(self.t("lbl_effort"))
        self.lbl_custom_budget.setText(self.t("lbl_custom_budget"))
        self.chk_mtp.setText(self.t("chk_mtp_ supported") if (self.active_model_info and self.active_model_info.get("has_mtp")) else self.t("chk_mtp_none"))
        self.chk_enable_draft.setText(self.t("chk_draft"))
        self.btn_draft_pick.setText(self.t("btn_pick_draft"))
        self.grp_samp.setTitle(self.t("grp_samp"))
        self.lbl_temp_title.setText(self.t("lbl_temp"))
        self.lbl_seed_title.setText(self.t("lbl_seed"))

        self.lbl_hw_cpu_ok.setText(self.t("hw_cpu_ok"))
        self.lbl_hw_ram.setText(f"{self.t('hw_sys_ram')} {self.hw_info['ram_gb']} GB")
        self.lbl_hw_vram.setText(f"{self.t('hw_tot_vram')} {self.hw_info['total_vram_gb']} GB")
        self.grp_gpus.setTitle(f"{self.t('hw_gpus')} ({len(self.hw_info['gpus'])})")
        self.lbl_hw_split.setText(self.t("hw_split"))
        self.grp_mon.setTitle(self.t("hw_mon"))

        self.grp_srv_mgmt.setTitle(self.t("srv_mgmt"))
        self.lbl_srv_state.setText(self.t("srv_state_on") if self.server_service_enabled else self.t("srv_state_off"))
        self.btn_srv_toggle.setText(self.t("btn_srv_stop") if self.server_service_enabled else self.t("btn_srv_start"))
        self.grp_srv_net.setTitle(self.t("srv_net_grp"))
        self.lbl_port_title.setText(self.t("lbl_port"))
        self.btn_copy_url.setText(self.t("btn_copy_api"))
        self.chk_lan.setText(self.t("chk_lan"))
        self.chk_cors.setText(self.t("chk_cors"))
        self.chk_tools.setText(self.t("chk_tools"))
        self.grp_srv_logs.setTitle(self.t("srv_logs"))
        self.update_endpoint_display()

        self.input_hf.setPlaceholderText(self.t("hf_placeholder"))
        self.btn_hf_search.setText(self.t("btn_search"))
        self.btn_hf_trend.setText(self.t("btn_hf_trend"))
        self.btn_hf_dl.setText(self.t("btn_hf_dl"))
        self.btn_hf_likes.setText(self.t("btn_hf_likes"))
        self.btn_hf_new.setText(self.t("btn_hf_new"))
        self.lbl_hf_models.setText(self.t("hf_models_lbl"))
        self.lbl_hf_files.setText(self.t("hf_files_lbl"))

        self.lbl_dl_header.setText(f"<b>{self.t('dl_active_grp')}</b>")
        self.lbl_dl_empty.setText(self.t("dl_empty"))

        self.lbl_tel_phase.setText(self.t("tel_waiting"))

        self.lbl_settings_header.setText(self.t("settings_title"))
        self.lbl_tel_speed.setText(self.t("speed_prefix").format(val="0.0"))
        if not self.active_model_info:
            self.lbl_mem_estimate.setText(self.t("mem_est_initial"))
        else:
            self.recalculate_memory_estimate()
        self.btn_back_main.setText(self.t("btn_back_main"))
        self.grp_set_lang.setTitle(self.t("set_grp_lang"))
        self.lbl_ui_lang.setText(self.t("lbl_ui_lang"))
        self.grp_set_sys.setTitle(self.t("set_grp_sys"))
        self.chk_autostart.setText(self.t("chk_autostart"))
        self.btn_install_desktop.setText(self.t("btn_install_desktop"))
        self.grp_set_hf.setTitle(self.t("set_grp_hf"))
        self.lbl_hf_token.setText(self.t("lbl_hf_token"))

        if self.runner_ref:
            self.runner_ref.refresh_menu_labels()

    def open_metadata_inspector(self):
        if not self.active_model_info:
            QMessageBox.information(self, "Tray AI", "Lütfen önce Modeller sekmesinden bir model seçin.")
            return
        dlg = MetadataInspectorDialog(self, self.active_model_info)
        dlg.exec()

    def autotune_for_hardware(self):
        if not self.active_model_info:
            QMessageBox.information(self, "Tray AI", "Lütfen önce Modeller sekmesinden bir model seçin.")
            return
        info = self.active_model_info
        layers = info.get("total_layers", 32)
        max_ctx = info.get("max_context", 8192)
        size_gb = info.get("size_gb", 4.0)
        ram_gb = self.hw_info.get("ram_gb", 16.0)

        self.slider_ngl.setValue(layers)
        if ram_gb >= 64:
            self.slider_ctx.setValue(min(max_ctx, 65536 if size_gb < 35 else 32768))
            self.cb_cache_k.setCurrentText("q8_0")
            self.cb_cache_v.setCurrentText("q8_0")
        elif ram_gb >= 32:
            self.slider_ctx.setValue(min(max_ctx, 32768 if size_gb < 20 else 16384))
            self.cb_cache_k.setCurrentText("q8_0")
            self.cb_cache_v.setCurrentText("q8_0")
        else:
            self.slider_ctx.setValue(min(max_ctx, 8192))
            self.cb_cache_k.setCurrentText("q4_0")
            self.cb_cache_v.setCurrentText("q4_0")

        self.chk_fa.setChecked(True)
        self.chk_cont_batch.setChecked(True)
        self.chk_mmap.setChecked(True)
        self.recalculate_memory_estimate()

    def recalculate_memory_estimate(self):
        if not self.active_model_info:
            return
        est = estimate_memory_usage_gb(
            self.active_model_info,
            self.spin_ctx.value(),
            self.spin_ngl.value(),
            self.cb_cache_k.currentText(),
            self.cb_cache_v.currentText()
        )
        sys_ram = max(1.0, self.hw_info.get("ram_gb", 32.0))
        pct = min(100, int((est["total_gb"] / sys_ram) * 100))
        self.bar_mem_estimate.setValue(pct)

        if pct < 75:
            status_icon = self.t("status_fits")
        elif pct < 92:
            status_icon = self.t("status_borderline")
        else:
            status_icon = self.t("status_insufficient")

        self.lbl_mem_estimate.setText(
            self.t("mem_est_format").format(
                total=est['total_gb'],
                model=self.active_model_info['size_gb'],
                kv=est['kv_gb'],
                status=status_icon,
                pct=pct
            )
        )

    def open_model_in_file_manager(self):
        if not self.selected_model_path or not os.path.exists(self.selected_model_path):
            QMessageBox.information(self, "Tray AI", "Lütfen önce listeden bir model seçin.")
            return
        folder = os.path.dirname(self.selected_model_path)
        subprocess.Popen(["xdg-open", folder])

    def open_root_folder_in_file_manager(self):
        folder = self.cfg.get("last_folder", "")
        if folder and os.path.isdir(folder):
            subprocess.Popen(["xdg-open", folder])
        elif self.selected_model_path and os.path.exists(self.selected_model_path):
            subprocess.Popen(["xdg-open", os.path.dirname(self.selected_model_path)])

    def delete_model_by_path(self, target_path):
        if not target_path or not os.path.exists(target_path):
            return

        m_name = os.path.basename(target_path)
        ans = QMessageBox.question(
            self,
            "Modeli Silmeyi Onayla",
            f"<b>{m_name}</b> dosyası diskten kalıcı olarak silinecek!\n\nEmin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            if self.server_mgr.is_running() and self.selected_model_path == target_path:
                self.unload_current_model()

            try:
                os.remove(target_path)
                if hasattr(self, "cache_mgr"):
                    with self.cache_mgr._get_conn() as conn:
                        conn.execute("DELETE FROM models WHERE path = ?", (target_path,))
                
                if target_path in self.loaded_models:
                    del self.loaded_models[target_path]
                
                if self.selected_model_path == target_path:
                    self.selected_model_path = None
                    self.active_model_info = None

                self.refresh_model_list_view()
                QMessageBox.information(self, "Silindi", f"'{m_name}' başarıyla diskten silindi.")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Dosya silinemedi:\n{e}")

    def delete_selected_model_file(self):
        if not self.selected_model_path or not os.path.exists(self.selected_model_path):
            QMessageBox.information(self, "Tray AI", "Lütfen önce silmek istediğiniz modeli seçin.")
            return

        m_name = os.path.basename(self.selected_model_path)
        ans = QMessageBox.question(
            self,
            "Modeli Silmeyi Onayla",
            f"<b>{m_name}</b> dosyası diskten kalıcı olarak silinecek!\n\nEmin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            if self.server_mgr.is_running():
                self.unload_current_model()

            try:
                os.remove(self.selected_model_path)
                if hasattr(self, "cache_mgr"):
                    with self.cache_mgr._get_conn() as conn:
                        conn.execute("DELETE FROM models WHERE path = ?", (self.selected_model_path,))
                QMessageBox.information(self, "Silindi", f"{m_name} başarıyla diskten silindi.")
                self.selected_model_path = None
                self.active_model_info = None
                folder = self.cfg.get("last_folder", "")
                if folder:
                    self.load_from_sqlite_instant(folder)
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Dosya silinemedi:\n{e}")

    def choose_draft_model(self):
        last_dir = self.cfg.get("last_folder", os.path.expanduser("~"))
        f, _ = QFileDialog.getOpenFileName(self, "Draft Model (.gguf)", last_dir, "GGUF (*.gguf)")
        if f:
            self.selected_draft_path = f
            self.lbl_draft_file.setText(os.path.basename(f))

    def choose_model_folder(self):
        start_dir = self.cfg.get("last_folder", "") or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(self, "GGUF Folder", start_dir)
        if folder:
            self.cfg["last_folder"] = folder
            save_json(CONFIG_FILE, self.cfg)
            self.lbl_folder.setText(f".../{os.path.basename(folder)}")
            self.load_from_sqlite_instant(folder)

    def force_rescan_models(self):
        folder = self.cfg.get("last_folder", "")
        if not folder or not os.path.isdir(folder):
            return
        if os.path.exists(self.cache_mgr.db_path):
            os.remove(self.cache_mgr.db_path)
            self.cache_mgr._init_db()
        self.load_from_sqlite_instant(folder)

    def load_from_sqlite_instant(self, folder):
        self.list_models.clear()
        self.loaded_models.clear()
        cached_models = self.cache_mgr.get_all_by_folder(folder)
        for m in cached_models:
            p = m["path"]
            # Sadece var olan ve mmproj olmayan modelleri yükle
            if os.path.exists(p) and "mmproj" not in os.path.basename(p).lower():
                self.loaded_models[p] = m
        self.refresh_model_list_view()

        self.scanner_thread = FastScannerThread(folder, self.cache_mgr)
        self.scanner_thread.new_model_found.connect(self.on_bg_model_found)
        self.scanner_thread.start()

    def on_bg_model_found(self, info):
        p = info["path"]
        if p not in self.loaded_models and "mmproj" not in os.path.basename(p).lower():
            self.loaded_models[p] = info
            self.refresh_model_list_view()

    def refresh_model_list_view(self):
        self.list_models.clear()
        search_txt = self.input_model_search.text().strip().lower() if hasattr(self, "input_model_search") else ""
        filter_idx = self.cb_model_filter.currentIndex() if hasattr(self, "cb_model_filter") else 0
        sort_idx = self.cb_model_sort.currentIndex() if hasattr(self, "cb_model_sort") else 0

        models = list(self.loaded_models.values())

        filtered = []
        for info in models:
            extra = info.get("extra_meta", {})
            if search_txt:
                haystack = f"{info['filename']} {info['arch']} {info['quant']} {info.get('publisher', '')}".lower()
                if search_txt not in haystack:
                    continue
            if filter_idx == 1 and not info.get("has_mtp"):
                continue
            elif filter_idx == 2 and not info.get("has_yarn"):
                continue
            elif filter_idx == 3 and not info.get("has_thinking"):
                continue
            elif filter_idx == 4 and not info.get("has_tools"):
                continue
            elif filter_idx == 5 and extra.get("expert_count", 0) <= 0:
                continue
            elif filter_idx == 6 and not info.get("has_vision"):
                continue
            filtered.append(info)

        if sort_idx == 0:
            filtered.sort(key=lambda x: x["filename"].lower())
        elif sort_idx == 1:
            filtered.sort(key=lambda x: x["size_gb"])
        elif sort_idx == 2:
            filtered.sort(key=lambda x: x["size_gb"], reverse=True)
        elif sort_idx == 3:
            filtered.sort(key=lambda x: x.get("max_context", 0), reverse=True)

        total_gb = round(sum(m["size_gb"] for m in filtered), 2)
        if hasattr(self, "lbl_models_summary"):
            self.lbl_models_summary.setText(
                self.t("models_summary_format").format(
                    shown=len(filtered),
                    total=len(models),
                    size=total_gb
                )
            )

        for info in filtered:
            self._insert_model_widget_item(info)

    def _insert_model_widget_item(self, info):
        extra = info.get("extra_meta", {})
        fn = info['filename']
        quant = info.get('quant', 'GGUF')

        clean_name = fn
        if clean_name.lower().endswith(".gguf"):
            clean_name = clean_name[:-5]
        
        for q_pattern in [quant, quant.lower(), quant.upper()]:
            if q_pattern and q_pattern != "Bilinmiyor":
                clean_name = clean_name.replace(f"-{q_pattern}", "").replace(f"_{q_pattern}", "").replace(f".{q_pattern}", "")
        clean_name = clean_name.strip("-_ .")

        badges = []
        pub = info.get("publisher", "Bilinmiyor")
        if pub != "Bilinmiyor":
            badges.append(f"🏢 {pub}")
        if extra.get("expert_count", 0) > 0:
            badges.append(f"🧩 MoE ({extra.get('expert_used_count', 0)}/{extra.get('expert_count', 0)})")
        if info.get("has_mtp"):
            badges.append(f"⚡ MTP ({info.get('mtp_layers', 1)}L)")
        if info.get("has_yarn"):
            badges.append("🧶 YaRN")
        if info.get("has_thinking"):
            badges.append("🧠 Düşünce")
        if info.get("has_tools"):
            badges.append("🔧 Araçlar")
        if info.get("has_vision"):
            badges.append("👁️ Görsel")

        rec_t = info.get("recommended_temp", 0.70)
        badges.append(f"🌡️ T:{rec_t:.2f}")

        badge_str = " • ".join(badges)
        ctx_k = f"{info['max_context'] // 1024}K" if info["max_context"] >= 1024 else str(info["max_context"])

        from PyQt6.QtCore import QSize
        row_widget = QWidget()
        row_widget.setStyleSheet("background: transparent;")
        row_layout = QVBoxLayout(row_widget)
        row_layout.setContentsMargins(8, 8, 8, 8)
        row_layout.setSpacing(5)

        # Üst Satır: Model Adı + [QUANT] + [GGUF] .... Boyut (GB)
        top_line = QHBoxLayout()
        top_line.setSpacing(6)
        top_line.setContentsMargins(0, 0, 0, 0)

        lbl_name = QLabel(f"<b>{clean_name}</b>")
        lbl_name.setStyleSheet("font-size: 13px; color: #c0caf5; font-weight: bold;")
        top_line.addWidget(lbl_name)

        # Quant seviyesine göre akıllı renk kodlaması
        q_up = str(quant).upper()
        if "Q8" in q_up:
            q_bg = "#e0af68" # Turuncu / Ağır
            q_fg = "#15161e"
        elif any(k in q_up for k in ["Q5", "Q6"]):
            q_bg = "#7aa2f7" # Mavi / Dengeli
            q_fg = "#15161e"
        elif any(k in q_up for k in ["F16", "BF16", "F32"]):
            q_bg = "#bb9af7" # Mor / Tam Hassasiyet
            q_fg = "#15161e"
        else:
            q_bg = "#2ac3de" # Camgöbeği / Hızlı 4-bit
            q_fg = "#15161e"

        lbl_quant = QLabel(f" {quant} ")
        lbl_quant.setStyleSheet(
            f"background: {q_bg}; color: {q_fg}; font-weight: bold; font-size: 10px; "
            "border-radius: 4px; padding: 1px 5px;"
        )
        top_line.addWidget(lbl_quant)

        lbl_format = QLabel(" GGUF ")
        lbl_format.setStyleSheet(
            "background: #1f2335; color: #7aa2f7; font-weight: bold; font-size: 10px; "
            "border-radius: 4px; padding: 1px 5px; border: 1px solid #3b4261;"
        )
        top_line.addWidget(lbl_format)
        top_line.addStretch()

        lbl_size = QLabel(f"<b>{info['size_gb']} GB</b>")
        lbl_size.setStyleSheet("color: #73daca; font-size: 11px; font-weight: bold; padding-right: 6px;")
        top_line.addWidget(lbl_size)

        # 3 Noktalı (⋮) Aksiyon Menüsü Butonu
        btn_dots = QPushButton("⋮")
        btn_dots.setFixedSize(24, 24)
        btn_dots.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_dots.setToolTip("Model İşlemleri")
        btn_dots.setStyleSheet("""
            QPushButton {
                background: #1f2335;
                border: 1px solid #3b4261;
                border-radius: 12px;
                color: #a9b1d6;
                font-size: 15px;
                font-weight: bold;
                padding-bottom: 2px;
            }
            QPushButton:hover {
                background: #3b4261;
                border-color: #7aa2f7;
                color: #7dcfff;
            }
        """)

        def show_item_menu(m_path=info["path"]):
            menu = QMenu(row_widget)
            act_load = menu.addAction("🚀 Modeli Yükle")
            act_folder = menu.addAction("📁 Klasörde Göster")
            act_inspect = menu.addAction("🔍 Metadata İncele")
            menu.addSeparator()
            act_del = menu.addAction("🗑️ Diskten Kalıcı Olarak Sil")

            chosen = menu.exec(btn_dots.mapToGlobal(QPoint(0, btn_dots.height())))
            if chosen == act_load:
                self.select_and_apply_model(m_path)
                self.load_selected_model()
            elif chosen == act_folder:
                subprocess.Popen(["xdg-open", os.path.dirname(m_path)])
            elif chosen == act_inspect:
                self.select_and_apply_model(m_path)
                self.open_metadata_inspector()
            elif chosen == act_del:
                self.delete_model_by_path(m_path)

        btn_dots.clicked.connect(lambda _, p=info["path"]: show_item_menu(p))
        top_line.addWidget(btn_dots)

        row_layout.addLayout(top_line)

        # Alt Satır: Mimari tekrarı kaldırıldı, doğrudan Katman ve Ctx ile başlar
        bottom_str = f"{info['total_layers']} Katman • Ctx: {ctx_k}"
        if badge_str:
            bottom_str += f" • {badge_str}"

        lbl_meta = QLabel(bottom_str)
        lbl_meta.setStyleSheet("color: #9aa5ce; font-size: 11px;")
        lbl_meta.setWordWrap(False)
        row_layout.addWidget(lbl_meta)

        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, info["path"])
        item.setSizeHint(QSize(row_widget.sizeHint().width(), 64))

        self.list_models.addItem(item)
        self.list_models.setItemWidget(item, row_widget)

    def on_rope_scaling_changed(self):
        if not self.active_model_info:
            return
        scaling_type = self.cb_rope_scaling.currentText()
        base_ctx = self.active_model_info.get("base_context", self.active_model_info.get("max_context", 4096))
        scale = self.spin_rope_scale.value()

        if scaling_type in ("yarn", "linear") and scale > 1.0:
            target_max = int(base_ctx * scale)
        elif scaling_type == "yarn" or self.active_model_info.get("has_yarn"):
            target_max = max(base_ctx * 4, 262144)
        else:
            target_max = base_ctx

        self.slider_ctx.setRange(512, target_max)
        self.spin_ctx.setRange(512, target_max)
        self.recalculate_memory_estimate()

    def save_current_model_custom_config(self):
        if not self.selected_model_path:
            return
        if "per_model_cfg" not in self.cfg:
            self.cfg["per_model_cfg"] = {}

        m_cfg = {
            "ngl": self.spin_ngl.value(),
            "ctx": self.spin_ctx.value(),
            "temp": self.spin_temp.value(),
            "topp": self.spin_topp.value(),
            "minp": self.spin_minp.value(),
            "topk": self.spin_topk.value(),
            "threads": self.spin_threads.value(),
            "threads_batch": self.spin_threads_batch.value(),
            "batch": self.spin_batch.value(),
            "ubatch": self.spin_ubatch.value(),
            "cache_k": self.cb_cache_k.currentText(),
            "cache_v": self.cb_cache_v.currentText(),
            "fa": self.chk_fa.isChecked(),
            "mmap": self.chk_mmap.isChecked(),
            "mlock": self.chk_mlock.isChecked(),
            "prompt_cache": self.chk_prompt_cache.isChecked() if hasattr(self, "chk_prompt_cache") else True,
            "rep_pen": self.spin_rep_pen.value(),
            "rope_scaling": self.cb_rope_scaling.currentText(),
            "custom_flags": self.input_custom_flags.text().strip()
        }
        self.cfg["per_model_cfg"][self.selected_model_path] = m_cfg
        self.cfg["last_selected_model"] = self.selected_model_path
        save_json(CONFIG_FILE, self.cfg)

    def restore_model_custom_config(self, path):
        saved = self.cfg.get("per_model_cfg", {}).get(path, {})
        if not saved:
            return False

        if "ngl" in saved: self.spin_ngl.setValue(saved["ngl"])
        if "ctx" in saved: self.spin_ctx.setValue(saved["ctx"])
        if "temp" in saved: self.spin_temp.setValue(saved["temp"])
        if "topp" in saved: self.spin_topp.setValue(saved["topp"])
        if "minp" in saved: self.spin_minp.setValue(saved["minp"])
        if "topk" in saved: self.spin_topk.setValue(saved["topk"])
        if "threads" in saved: self.spin_threads.setValue(saved["threads"])
        if "threads_batch" in saved: self.spin_threads_batch.setValue(saved["threads_batch"])
        if "batch" in saved: self.spin_batch.setValue(saved["batch"])
        if "ubatch" in saved: self.spin_ubatch.setValue(saved["ubatch"])
        if "cache_k" in saved: self.cb_cache_k.setCurrentText(saved["cache_k"])
        if "cache_v" in saved: self.cb_cache_v.setCurrentText(saved["cache_v"])
        if "fa" in saved: self.chk_fa.setChecked(saved["fa"])
        if "mmap" in saved: self.chk_mmap.setChecked(saved["mmap"])
        if "mlock" in saved: self.chk_mlock.setChecked(saved["mlock"])
        if "prompt_cache" in saved and hasattr(self, "chk_prompt_cache"):
            self.chk_prompt_cache.setChecked(saved["prompt_cache"])
        if "rep_pen" in saved: self.spin_rep_pen.setValue(saved["rep_pen"])
        if "rope_scaling" in saved: self.cb_rope_scaling.setCurrentText(saved["rope_scaling"])
        if "custom_flags" in saved: self.input_custom_flags.setText(saved["custom_flags"])
        return True

    def select_and_apply_model(self, path):
        if not path or path not in self.loaded_models:
            return

        # Önceki modelde yapılan değişiklikleri kaydet
        if getattr(self, "selected_model_path", None) and self.selected_model_path != path:
            self.save_current_model_custom_config()

        self.selected_model_path = path
        info = self.loaded_models[path]
        self.active_model_info = info
        extra_m = info.get("extra_meta", {})

        # Listede bu modeli görsel olarak seç
        for idx in range(self.list_models.count()):
            it = self.list_models.item(idx)
            if it and it.data(Qt.ItemDataRole.UserRole) == path:
                self.list_models.blockSignals(True)
                self.list_models.setCurrentItem(it)
                self.list_models.blockSignals(False)
                break

        mtp_badge = self.t("badge_mtp_active").format(layers=info.get('mtp_layers', 1)) if info.get("has_mtp") else self.t("badge_mtp_none")
        yarn_badge = self.t("badge_yarn_active") if info.get("has_yarn") else self.t("badge_yarn_none")
        sampler_src = extra_m.get("sampler_source", "Profil")

        self.lbl_model_meta_summary.setText(
            self.t("meta_summary_format").format(
                fn=info['filename'],
                arch=info['arch'].upper(),
                layers=info['total_layers'],
                ctx=f"{info.get('base_context', info['max_context']):,}",
                mtp=mtp_badge,
                yarn=yarn_badge,
                src=sampler_src,
                temp=info.get('recommended_temp', 0.70),
                topp=info.get('recommended_topp', 0.90),
                minp=info.get('recommended_minp', 0.05)
            )
        )

        layers = info.get("total_layers", 32)
        self.slider_ngl.setRange(0, layers)
        self.spin_ngl.setRange(0, layers)

        base_ctx = info.get("base_context", info.get("max_context", 4096))
        rope_scale = float(extra_m.get("rope_scale", 1.0))
        rope_type = extra_m.get("rope_scaling_type", "none")

        if rope_scale > 1.0 or "yarn" in rope_type or info.get("has_yarn"):
            max_effective_ctx = max(int(base_ctx * max(rope_scale, 4.0)), 262144)
            self.cb_rope_scaling.setCurrentText("yarn" if ("yarn" in rope_type or info.get("has_yarn")) else "linear")
        else:
            max_effective_ctx = base_ctx
            self.cb_rope_scaling.setCurrentText("Auto (Varsayılan)")

        self.slider_ctx.setRange(512, max_effective_ctx)
        self.spin_ctx.setRange(512, max_effective_ctx)

        # Varsayılan profil değerlerini ata
        self.spin_rope_base.setValue(float(extra_m.get("rope_freq_base", 10000.0)))
        self.spin_rope_scale.setValue(rope_scale)
        self.spin_temp.setValue(float(info.get("recommended_temp", 0.70)))
        self.spin_topp.setValue(float(info.get("recommended_topp", 0.90)))
        self.spin_minp.setValue(float(info.get("recommended_minp", 0.05)))
        self.spin_topk.setValue(int(info.get("recommended_top_k", 40)))
        self.slider_ngl.setValue(layers)
        self.slider_ctx.setValue(base_ctx)

        # Eğer kullanıcı bu modele özel ayar yapmışsa onları geri yükle
        has_custom = self.restore_model_custom_config(path)
        if not has_custom:
            self.cfg.setdefault("per_model_cfg", {})[path] = {"ngl": layers, "ctx": base_ctx}

        has_real_mtp = bool(info.get("has_mtp", False))
        self.chk_mtp.setEnabled(True)
        if has_real_mtp:
            mtp_l = max(1, int(info.get("mtp_layers", 1)))
            reason = extra_m.get("mtp_reason", "Algılandı")
            self.chk_mtp.setChecked(True)
            self.chk_mtp.setText(f"⚡ MTP ({mtp_l} Katman Spekülatif Tahmin) Aktif — [{reason}]")
            self.chk_mtp.setStyleSheet("color: #9ece6a; font-weight: bold;")
            self.chk_enable_draft.setChecked(False)
            self.spin_draft_max.setEnabled(True)
            self.spin_draft_max.setValue(3)
        else:
            self.chk_mtp.setChecked(False)
            self.chk_mtp.setText(self.t("chk_mtp_none"))
            self.chk_mtp.setStyleSheet("color: #a9b1d6;")
            self.chk_enable_draft.setEnabled(True)

        if info.get("has_thinking", False):
            self.cb_thinking_effort.setEnabled(True)
            self.cb_thinking_effort.setCurrentIndex(2)
        else:
            self.cb_thinking_effort.setEnabled(False)
            self.cb_thinking_effort.setCurrentIndex(0)
            self.spin_thinking_tokens.setEnabled(False)

        self.recalculate_memory_estimate()

    def on_gateway_request_switch_model(self, model_id):
        models = self.get_gateway_models_list()
        target_path = None
        for m in models:
            p = m["path"]
            clean_id = os.path.splitext(m["filename"])[0]
            if model_id.lower() == clean_id.lower() or model_id.lower() in clean_id.lower() or model_id.lower() in p.lower():
                target_path = p
                if p not in self.loaded_models:
                    self.loaded_models[p] = m
                break

        if target_path and os.path.exists(target_path):
            self.select_and_apply_model(target_path)
            self.load_selected_model()

    def on_model_selected(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        self.select_and_apply_model(path)

    def get_current_active_model_id(self):
        if self.selected_model_path and self.server_mgr.is_running():
            return os.path.splitext(os.path.basename(self.selected_model_path))[0]
        return ""

    def get_gateway_models_list(self):
        models_dict = {}
        for p, m in self.loaded_models.items():
            if os.path.exists(p):
                models_dict[p] = m

        try:
            all_cached = self.cache_mgr.get_all_cached_models()
            for m in all_cached:
                p = m["path"]
                if p not in models_dict and os.path.exists(p) and "mmproj" not in os.path.basename(p).lower():
                    models_dict[p] = m
        except Exception:
            pass
        return list(models_dict.values())

    def _track_model_loading_progress(self):
        if not self.server_mgr.is_running() or not self.selected_model_path:
            self.load_tracker_timer.stop()
            return

        target_gb = getattr(self, "_loading_target_gb", 0.0)
        if target_gb <= 0:
            return

        proc = getattr(self.server_mgr, "process", None)
        if not proc or proc.poll() is not None:
            self.load_tracker_timer.stop()
            return

        try:
            p = psutil.Process(proc.pid)

            # 1. Disk I/O okuma takibi (Bayt bazında)
            io_gb = 0.0
            try:
                cur_io = p.io_counters().read_bytes
                start_io = getattr(self, "_io_start_bytes", cur_io)
                io_gb = max(0.0, (cur_io - start_io) / (1024 ** 3))
            except Exception:
                pass

            # 2. VRAM / GTT artışı (Radeon 780M veya dGPU)
            vram_delta_gb = 0.0
            if hasattr(self, "gpu_vram_widgets"):
                for gid, w in self.gpu_vram_widgets.items():
                    c_idx = w.get("drm_card", gid)
                    is_ig = w.get("is_igpu", None)
                    cur_v = read_drm_vram_used_gb(c_idx, is_igpu=is_ig)
                    start_v = getattr(self, "_vram_start_map", {}).get(gid, cur_v)
                    vram_delta_gb += max(0.0, cur_v - start_v)

            # 3. Süreç RSS (Fiziksel RAM)
            rss_gb = p.memory_info().rss / (1024 ** 3)

            # Gerçek okunan veri (üç kaynaktan en güveniliri)
            loaded_gb = min(target_gb, max(io_gb, vram_delta_gb, rss_gb))

            # Canlı okuma hızı hesabı (MB/s)
            now = time.time()
            dt = max(0.1, now - getattr(self, "_last_track_time", now))
            last_loaded = getattr(self, "_last_loaded_gb", loaded_gb)
            speed_mb = max(0.0, ((loaded_gb - last_loaded) * 1024) / dt)
            self._last_loaded_gb = loaded_gb
            self._last_track_time = now

            # %0 - %85 aralığı: Model tensörlerinin diskten belleğe akışı
            raw_pct = min(1.0, loaded_gb / target_gb)
            calculated_pct = int(raw_pct * 85.0)

            cur_val = self.load_progress_bar.value()
            # Geri gitmeyi engelle, ancak asla yapay +1 ekleme!
            new_val = max(cur_val, calculated_pct)
            new_val = min(85, max(5, new_val))

            self.load_progress_bar.setValue(new_val)

            # Canlı dönen gösterge simgesi (donmadığını gösterir)
            glyphs = ["◐", "◓", "◑", "◒"]
            tick = getattr(self, "_anim_tick", 0) + 1
            self._anim_tick = tick
            g = glyphs[tick % len(glyphs)]

            speed_str = f" • {speed_mb:.0f} MB/s" if speed_mb >= 1.0 else ""
            self.lbl_load_stage.setText(f"{g} Yükleniyor: {loaded_gb:.2f} / {target_gb:.2f} GB (%{new_val}){speed_str}")
        except Exception:
            pass

    def load_selected_model(self):
        if not self.server_service_enabled:
            return
        if not self.selected_model_path or not os.path.exists(self.selected_model_path):
            return

        engine = "llama-server"
        ngl = self.spin_ngl.value()
        ctx = self.spin_ctx.value()
        port = getattr(self, 'upstream_port', self.spin_port.value() + 1)
        host = "0.0.0.0" if self.chk_lan.isChecked() else "127.0.0.1"

        if "per_model_cfg" not in self.cfg:
            self.cfg["per_model_cfg"] = {}
        self.save_current_model_custom_config()

        extra = [
            "-t", str(self.spin_threads.value()),
            "-tb", str(self.spin_threads_batch.value()),
            "-b", str(self.spin_batch.value()),
            "-ub", str(self.spin_ubatch.value()),
            "-np", str(self.spin_parallel.value()),
            "-ctk", self.cb_cache_k.currentText(),
            "-ctv", self.cb_cache_v.currentText(),
            "--temp", f"{self.spin_temp.value():.2f}",
            "--top-k", str(self.spin_topk.value()),
            "--top-p", f"{self.spin_topp.value():.2f}",
            "--min-p", f"{self.spin_minp.value():.2f}",
            "--repeat-penalty", f"{self.spin_rep_pen.value():.2f}",
            "--repeat-last-n", str(self.spin_rep_n.value()),
            "--presence-penalty", f"{self.spin_pres_pen.value():.2f}",
            "--frequency-penalty", f"{self.spin_freq_pen.value():.2f}",
            "-s", str(self.spin_seed.value()),
            "-fa", "on" if self.chk_fa.isChecked() else "off"
        ]

        if self.spin_rope_base.value() > 0:
            extra.extend(["--rope-freq-base", str(self.spin_rope_base.value())])
        if self.spin_rope_scale.value() > 0 and self.spin_rope_scale.value() != 1.0:
            extra.extend(["--rope-freq-scale", str(self.spin_rope_scale.value())])

        miro = self.cb_mirostat.currentIndex()
        if miro > 0:
            extra.extend(["--mirostat", str(miro)])

        if self.chk_cont_batch.isChecked(): extra.append("-cb")
        if not self.chk_mmap.isChecked(): extra.append("--no-mmap")
        if self.chk_mlock.isChecked(): extra.append("--mlock")
        if not self.chk_offload_kv.isChecked(): extra.append("-nkvo")

        if self.chk_tools.isChecked():
            extra.append("--jinja")
            extra.append("--special")

        active_gpu_ids = [str(gid) for gid, btn in self.gpu_toggles.items() if btn.isChecked()]
        env_vars = {}
        if not active_gpu_ids:
            ngl = 0
        else:
            devs_csv = ",".join(active_gpu_ids)
            env_vars["GGML_VK_VISIBLE_DEVICES"] = devs_csv
            env_vars["ROCR_VISIBLE_DEVICES"] = devs_csv
            env_vars["HIP_VISIBLE_DEVICES"] = devs_csv
            env_vars["CUDA_VISIBLE_DEVICES"] = devs_csv

            if len(active_gpu_ids) == 1:
                extra.extend(["--split-mode", "none", "--main-gpu", "0"])
            else:
                extra.extend(["--split-mode", self.cb_split_mode.currentData()])
                # 2 GPU aktifse kullanıcı tanımlı oranla --tensor-split ekle
                if len(active_gpu_ids) == 2:
                    ratio = getattr(self, "slider_gpu_ratio", None)
                    val = ratio.value() if ratio else 50
                    r0 = max(1, val)
                    r1 = max(1, 100 - val)
                    extra.extend(["-ts", f"{r0},{r1}"])

        if self.cb_thinking_effort.isEnabled():
            eff_idx = self.cb_thinking_effort.currentIndex()
            if eff_idx == 0: extra.extend(["--reasoning-budget", "0"])
            elif eff_idx == 1: extra.extend(["--reasoning-budget", "1024"])
            elif eff_idx == 2: extra.extend(["--reasoning-budget", "4096"])
            elif eff_idx == 3: extra.extend(["--reasoning-budget", "16384"])
            elif eff_idx == 4:
                extra.extend(["--reasoning-budget", str(self.spin_thinking_tokens.value())])

        if self.spin_dry_mult.value() > 0.0:
            extra.extend(["--dry-multiplier", f"{self.spin_dry_mult.value():.2f}", "--dry-base", f"{self.spin_dry_base.value():.2f}"])
        if self.spin_xtc_prob.value() > 0.0:
            extra.extend(["--xtc-probability", f"{self.spin_xtc_prob.value():.2f}", "--xtc-threshold", f"{self.spin_xtc_thresh.value():.2f}"])
        if self.spin_dynatemp.value() > 0.0:
            extra.extend(["--dynatemp-range", f"{self.spin_dynatemp.value():.2f}"])
        if self.spin_typical.value() < 1.0:
            extra.extend(["--typical", f"{self.spin_typical.value():.2f}"])

        if self.cb_rope_scaling.currentIndex() > 0:
            extra.extend(["--rope-scaling", self.cb_rope_scaling.currentText()])
        if self.spin_yarn_ext.value() >= 0.0:
            extra.extend(["--yarn-ext-factor", f"{self.spin_yarn_ext.value():.2f}"])

        if self.cb_chat_template.currentIndex() > 0:
            extra.extend(["--chat-template", self.cb_chat_template.currentText()])

        custom_f = self.input_custom_flags.text().strip()
        if custom_f:
            extra.extend(custom_f.split())

        # Otomatik mmproj (Vision Adaptör) Tespiti ve Entegrasyonu
        model_dir = os.path.dirname(self.selected_model_path)
        mmproj_path = None
        try:
            for cand in os.listdir(model_dir):
                if "mmproj" in cand.lower() and cand.lower().endswith(".gguf"):
                    mmproj_path = os.path.join(model_dir, cand)
                    break
        except Exception:
            pass

        if mmproj_path and os.path.exists(mmproj_path):
            extra.extend(["--mmproj", mmproj_path])

        # Model Alias (Uzak istemcilerde dosya yolu yerine temiz isim görünmesi için)
        clean_model_id = os.path.splitext(os.path.basename(self.selected_model_path))[0]
        extra.extend(["--alias", clean_model_id])

        # Prompt Caching llama-server tarafından dahili bellek slotlarında yerleşik (in-memory prefix-cache) olarak yürütülür.

        # Spekülatif Çıkarım / MTP Ayarları (LM Studio Standartları)
        draft_val = str(self.spin_draft_max.value()) if hasattr(self, "spin_draft_max") and self.spin_draft_max.isEnabled() else "3"
        if self.chk_mtp.isChecked():
            extra.extend([
                "--spec-type", "draft-mtp",
                "--spec-draft-n-max", draft_val,
                "--spec-draft-n-min", "0",
                "--spec-draft-p-min", "0",
                "--kv-unified"
            ])

        if self.chk_enable_draft.isChecked() and self.selected_draft_path:
            extra.extend(["-md", self.selected_draft_path, "--spec-draft-n-max", str(self.spin_draft_max.value())])

        # LM Studio Seviyesinde Performans Bayrakları (Flash Attention, Micro-batch, Fiziksel Thread)
        if "-fa" not in extra and "--flash-attn" not in extra:
            extra.append("-fa")
        if "-ub" not in extra and "--ubatch" not in extra:
            extra.extend(["-ub", "512"])
        if "-t" not in extra and "--threads" not in extra:
            extra.extend(["-t", "8"])

        self.txt_logs.clear()
        self.poller.set_port(port)
        self.poller.reset_ready()
        self.load_progress_bar.setValue(5)
        
        # Yükleme hedef boyutunu ve donanım başlangıçlarını kaydet
        model_size = os.path.getsize(self.selected_model_path) / (1024**3)
        if mmproj_path and os.path.exists(mmproj_path):
            model_size += os.path.getsize(mmproj_path) / (1024**3)
        self._loading_target_gb = max(0.5, model_size)

        # Kart bazlı başlangıç VRAM/GTT haritası
        self._vram_start_map = {}
        if hasattr(self, "gpu_vram_widgets"):
            for gid, w in self.gpu_vram_widgets.items():
                c_idx = w.get("drm_card", gid)
                is_ig = w.get("is_igpu", None)
                self._vram_start_map[gid] = read_drm_vram_used_gb(c_idx, is_igpu=is_ig)

        self._io_start_bytes = 0
        self._last_loaded_gb = 0.0
        self._last_track_time = time.time()
        self._anim_tick = 0

        self.lbl_load_stage.setText(f"⏳ Model okunuyor: 0.00 / {self._loading_target_gb:.2f} GB (%5)")
        self.set_status_badge("loading", self.t("srv_loading"))
        self.btn_drop_cache.setEnabled(False)
        tray_ref.setIcon(get_tray_icon("loading"))
        self.load_tracker_timer.start(250)

        try:
            total_l = self.active_model_info.get("total_layers", 32) if self.active_model_info else 32
            reader = self.server_mgr.start_model(
                engine_name=engine,
                model_path=self.selected_model_path,
                host=host,
                port=port,
                ngl=ngl,
                ctx=ctx,
                extra_flags=extra,
                env_vars=env_vars,
                total_layers=total_l
            )
            reader.log_line.connect(self.on_server_log)
            reader.load_progress.connect(self.on_load_progress)
            reader.server_ready.connect(self.on_model_ready)
            reader.server_stopped.connect(self.on_process_stopped)
            reader.tool_call_detected.connect(self.on_tool_call_log)

            self.btn_unload_model.setEnabled(True)
            self.btn_load_model.setText(self.t("btn_reload"))
        except Exception as e:
            self.btn_drop_cache.setEnabled(True)
            QMessageBox.critical(self, "Error", str(e))

    def unload_current_model(self):
        if hasattr(self, 'load_tracker_timer'): self.load_tracker_timer.stop()
        self.server_mgr.stop_model()
        self.poller.reset_ready()
        self.load_progress_bar.setValue(0)
        self.bar_prompt_activity.setValue(0)
        self.lbl_load_stage.setText(self.t("lbl_no_model"))
        self.lbl_tel_phase.setText(self.t("tel_waiting"))
        self.lbl_prompt_read.setText(self.t("prompt_read_prefix").format(val=0))
        self.lbl_token_counter.setText(self.t("tokens_prefix").format(val=0))
        self.btn_unload_model.setEnabled(False)
        self.btn_drop_cache.setEnabled(True)
        self.btn_load_model.setText(self.t("btn_load"))
        if self.server_service_enabled:
            self.set_status_badge("unloaded", self.t("srv_unloaded"))
            tray_ref.setIcon(get_tray_icon("ready"))

    def clear_server_logs(self):
        if hasattr(self, "_raw_log_lines"):
            self._raw_log_lines.clear()
        self.txt_logs.clear()

    def copy_all_logs(self):
        text = self.txt_logs.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.set_status_badge("ready" if self.server_mgr.is_running() else "waiting", "📋 Loglar Kopyalandı!")
            QTimer.singleShot(2000, lambda: self.set_status_badge("ready" if self.server_mgr.is_running() else "waiting", self.t("srv_ready") if self.server_mgr.is_running() else self.t("srv_wait_model")))

    def filter_server_logs(self):
        if not hasattr(self, "_raw_log_lines"):
            return
        query = self.input_log_filter.text().strip().lower()
        self.txt_logs.clear()
        if not query:
            self.txt_logs.setPlainText("\n".join(self._raw_log_lines))
        else:
            matched = [line for line in self._raw_log_lines if query in line.lower()]
            self.txt_logs.setPlainText("\n".join(matched))

        if self.chk_log_autoscroll.isChecked():
            self.txt_logs.verticalScrollBar().setValue(self.txt_logs.verticalScrollBar().maximum())

    def on_server_log(self, line):
        if not hasattr(self, "_raw_log_lines"):
            self._raw_log_lines = []
        self._raw_log_lines.append(line)
        if len(self._raw_log_lines) > 3000:
            self._raw_log_lines.pop(0)

        query = self.input_log_filter.text().strip().lower() if hasattr(self, "input_log_filter") else ""
        if not query or query in line.lower():
            self.txt_logs.appendPlainText(line)
            if hasattr(self, "chk_log_autoscroll") and self.chk_log_autoscroll.isChecked():
                self.txt_logs.verticalScrollBar().setValue(self.txt_logs.verticalScrollBar().maximum())

    def on_load_progress(self, pct, stage_text):
        if pct >= self.load_progress_bar.value():
            self.load_progress_bar.setValue(pct)
            self.lbl_load_stage.setText(f"⏳ {stage_text} (%{pct})")

    def on_health_loading_tick(self):
        pass

    def on_health_confirmed_ready(self):
        # Uygulama kendi bir model başlatmadıysa yetim sinyallere aldanma
        if not self.server_mgr.is_running():
            self.poller.reset_ready()
            return

        if self.server_mgr.reader_thread:
            self.server_mgr.reader_thread.mark_ready_external()
        else:
            self.on_model_ready()

    def on_model_ready(self):
        if hasattr(self, "load_tracker_timer"):
            self.load_tracker_timer.stop()
        self.load_progress_bar.setValue(100)
        m_name = os.path.basename(self.selected_model_path) if self.selected_model_path else "Model"
        self.lbl_load_stage.setText(f"✅ {m_name} (%100)")
        self.lbl_tel_phase.setText(self.t("tel_waiting"))
        self.set_status_badge("ready", self.t("srv_ready"))
        self.btn_drop_cache.setEnabled(False)
        self.btn_unload_model.setEnabled(True)
        tray_ref.setIcon(get_tray_icon("active"))

    def on_tool_call_log(self, msg):
        self.remote_tool_active = True
        self.lbl_tel_phase.setText(self.t("tel_tool"))

    def on_live_telemetry(self, info):
        is_proc = info["is_processing"]
        phase = info["phase"]
        n_ctx = info["n_ctx"]
        n_past = info["n_past"]
        tokens_gen = info.get("tokens_generated", 0)
        tg_speed = info.get("tg_speed", 0.0)
        pp_speed = info.get("pp_speed", 0.0)
        is_tool = info.get("is_tool_call", False) or self.remote_tool_active

        self.lbl_ctx_usage.setText(self.t("ctx_prefix").format(past=n_past, ctx=n_ctx))

        if is_proc:
            tray_ref.setIcon(get_tray_icon("generating"))
            if phase == "prompt":
                self.remote_tool_active = False
                pct = info["prompt_pct"]
                self.lbl_tel_phase.setText(self.t("tel_reading"))
                self.lbl_prompt_read.setText(self.t("prompt_read_prefix").format(val=pct))
                self.lbl_token_counter.setText(self.t("tokens_prefix").format(val=0))
                self.bar_prompt_activity.setValue(pct)
                if pp_speed > 0:
                    self.lbl_tel_speed.setText(self.t("speed_pp").format(val=f"{pp_speed:.1f}"))
            else:
                self.lbl_prompt_read.setText(self.t("prompt_read_prefix").format(val=100))
                self.bar_prompt_activity.setValue(100)
                if is_tool:
                    self.lbl_tel_phase.setText(self.t("tel_tool"))
                else:
                    self.lbl_tel_phase.setText(self.t("tel_gen"))
                    self.lbl_token_counter.setText(self.t("tokens_prefix").format(val=tokens_gen))

                if tg_speed > 0:
                    self.lbl_tel_speed.setText(self.t("speed_tg").format(val=f"{tg_speed:.1f}"))
        else:
            self.remote_tool_active = False
            tray_ref.setIcon(get_tray_icon("active"))
            self.lbl_tel_phase.setText(self.t("tel_done"))
            if tg_speed > 0:
                self.lbl_tel_speed.setText(self.t("speed_prefix").format(val=f"{tg_speed:.1f}"))

    def on_process_stopped(self, code):
        if hasattr(self, 'load_tracker_timer'): self.load_tracker_timer.stop()
        self.btn_drop_cache.setEnabled(True)
        self.btn_unload_model.setEnabled(False)
        if self.load_progress_bar.value() < 100 and code != 0:
            self.lbl_load_stage.setText(f"❌ Code: {code} (Check Server Logs)")
            self.set_status_badge("error", self.t("srv_error"))
            tray_ref.setIcon(get_tray_icon("stopped"))


class MainRunner:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        if os.path.exists(ICON_PATH):
            self.app.setWindowIcon(QIcon(ICON_PATH))

        global tray_ref
        self.tray = QSystemTrayIcon(get_tray_icon("ready"), self.app)
        tray_ref = self.tray
        self.tray.setToolTip("Tray AI LLM Server")

        self.window = TrayAIApp(self)

        self.menu = QMenu()
        self.act_toggle = QAction(self.menu)
        self.act_toggle.triggered.connect(self.toggle_popup)
        self.act_settings = QAction(self.menu)
        self.act_settings.triggered.connect(self.open_settings)
        self.act_exit = QAction(self.menu)
        self.act_exit.triggered.connect(self.exit_app)

        self.menu.addAction(self.act_toggle)
        self.menu.addAction(self.act_settings)
        self.menu.addSeparator()
        self.menu.addAction(self.act_exit)

        self.refresh_menu_labels()
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.on_tray_clicked)
        self.tray.show()

    def refresh_menu_labels(self):
        if not hasattr(self, "act_toggle"):
            return
        self.act_toggle.setText(self.window.t("tray_toggle"))
        self.act_settings.setText(self.window.t("tray_settings"))
        self.act_exit.setText(self.window.t("tray_exit"))

    def open_settings(self):
        if not self.window.isVisible():
            self.toggle_popup()
        self.window.view_stack.setCurrentIndex(1)

    def toggle_popup(self):
        if self.window.isVisible():
            self.window.hide()
        else:
            cursor_pos = QCursor.pos()
            screen = QGuiApplication.screenAt(cursor_pos) or QGuiApplication.primaryScreen()
            geo = screen.availableGeometry()

            win_w = self.window.width()
            win_h = min(self.window.height(), geo.height() - 20)
            self.window.resize(win_w, win_h)

            target_x = cursor_pos.x() - (win_w // 2)
            x = max(geo.left() + 10, min(target_x, geo.right() - win_w - 10))

            if cursor_pos.y() < geo.center().y():
                y = max(geo.top() + 10, min(cursor_pos.y() + 25, geo.bottom() - win_h - 10))
            else:
                y = max(geo.top() + 10, min(cursor_pos.y() - win_h - 25, geo.bottom() - win_h - 10))

            self.window.move(x, y)
            self.window.show()
            self.window.raise_()
            self.window.activateWindow()

    def on_tray_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_popup()

    def exit_app(self):
        self.window.poller.stop()
        if hasattr(self.window, 'api_gateway'): self.window.api_gateway.stop()
        if self.window.server_mgr.is_running():
            self.window.server_mgr.stop_model()
        self.app.quit()

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    runner = MainRunner()
    runner.run()
