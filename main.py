import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import json
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
from PyQt6.QtGui import QIcon, QAction, QColor, QPixmap, QCursor, QGuiApplication, QPainter, QBrush

from core.cache_manager import CacheManager
from core.gguf_parser import analyze_gguf_file, estimate_memory_usage_gb
from core.server_manager import ServerManager, TelemetryPoller
from core.hardware import get_system_hardware
from core.hf_downloader import HFSearchWorker, HFFilesWorker, DownloadWorker
from core.engine_updater import EngineVersionChecker, EngineUpdateWorker
from ui.styles import DARK_STYLE

USER_ENGINES_DIR = os.path.expanduser("~/.local/share/tray-ai/engines")
os.makedirs(USER_ENGINES_DIR, exist_ok=True)
_bundled_eng = USER_ENGINES_DIR
if os.path.isdir(_bundled_eng):
    import shutil
    for _f in os.listdir(_bundled_eng):
        _src = os.path.join(_bundled_eng, _f)
        _dst = os.path.join(USER_ENGINES_DIR, _f)
        if os.path.isfile(_src) and not os.path.exists(_dst):
            shutil.copy2(_src, _dst)
            if "llama-server" in _f:
                os.chmod(_dst, 0o755)

CONFIG_DIR = os.path.expanduser("~/.config/tray-ai")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
ICON_PATH = os.path.join(BASE_DIR, "assets", "tray-ai.svg")

# =========================================================================
# ÇOKLU DİL SÖZLÜĞÜ (TR / EN)
# =========================================================================
I18N = {
    "tr": {
        "drag_hint": "(Taşımak için sürükleyin)",
        "srv_wait_model": "● Sunucu Açık (Model Bekleniyor)",
        "srv_loading": "● Model Yükleniyor...",
        "srv_ready": "● Model Yüklü & Hazır",
        "srv_stopped": "● Sunucu Kapalı",
        "srv_unloaded": "● Sunucu Açık (Model Boşaltıldı)",
        "srv_error": "● Hata Oluştu",
        "tab_models": "Modeller",
        "tab_config": "Model Ayarları",
        "tab_hw": "Donanım",
        "tab_server": "Sunucu",
        "tab_hf": "Hugging Face",
        "tab_dl": "İndirilenler",
        "btn_pick_dir": "📁 Klasör Seç",
        "btn_rescan": "🔄 Yeniden Analiz Et",
        "lbl_no_folder": "Seçilmedi",
        "lbl_engine": "<b>Çalıştırma Motoru:</b>",
        "lbl_no_meta": "Model Seçilmedi — Metadata bekleniyor...",
        "grp_ctx": "1. Bağlam (Context) & GPU Yük Aktarma",
        "lbl_ctx": "Bağlam Uzunluğu (-c):",
        "lbl_ngl": "GPU Yük Aktarma Katmanı (-ngl):",
        "grp_kv": "2. K Cache / V Cache Nicemleme & Bellek Optimizasyonu",
        "chk_kv_gpu": "KV Cache GPU'da Tut",
        "chk_mmap": "mmap() Kullan",
        "chk_mlock": "mlock() Bellekte Kilitle",
        "grp_batch": "3. CPU Çekirdek, Parti (Batch) & RoPE Frekans Ayarları",
        "lbl_parallel": "Paralel İstek Slotu (-np):",
        "grp_spec": "4. Düşünce Eforu (Reasoning) & Spekülatif Çözme (MTP / Draft)",
        "lbl_effort": "Düşünce Eforu:",
        "eff_items": ["Kapalı", "Düşük (Low)", "Orta (Medium)", "Yüksek (High)", "Özel Bütçe"],
        "lbl_custom_budget": "Özel Bütçe:",
        "chk_mtp_ supported": "MTP (Multi-Token Prediction) Katmanlarını Aktif Et (Destekleniyor)",
        "chk_mtp_none": "Modelde MTP Desteği Yok",
        "chk_draft": "Draft Model:",
        "btn_pick_draft": "Model Seç...",
        "grp_samp": "5. Örnekleyiciler (Temperature, Top-K/P, Min-P, Cezalar, Seed)",
        "lbl_temp": "Sıcaklık (Temp):",
        "lbl_seed": "Seed (Tohum):",
        "hw_cpu_ok": "<b>İşlemci (CPU)</b> <span style='color:#9ece6a;'>✓ Uyumlu</span>",
        "hw_isa": "Komut Setleri:",
        "hw_sys_ram": "<b>Sistem RAM:</b>",
        "hw_tot_vram": "<b>Toplam VRAM:</b>",
        "hw_gpus": "Algılanan GPU Donanımları",
        "hw_split": "Çoklu GPU Dağıtım Stratejisi:",
        "hw_split_items": ["Eşit / Katman Bölme (Layer Split)", "Satır Bölme (Row Split)", "Tek GPU (Yalnızca İlk Aktif Kart)"],
        "hw_mon": "Canlı Kaynak İzleyici (Resource Monitor)",
        "srv_mgmt": "Sunucu Servis Yönetimi",
        "srv_state_on": "🟢 <b>Sunucu Servisi: AKTİF</b>",
        "srv_state_off": "🔴 <b>Sunucu Servisi: DURDURULDU</b>",
        "btn_srv_stop": "Sunucuyu Durdur",
        "btn_srv_start": "Sunucuyu Başlat",
        "srv_net_grp": "Ağ, IP, Port ve Ajan (MCP/Tool) Konfigürasyonu",
        "lbl_port": "Sunucu Portu:",
        "btn_copy_api": "📋 API Adresini Kopyala",
        "chk_lan": "Yerel Ağda Sun (0.0.0.0 - Ağdaki diğer cihazlar erişebilsin)",
        "chk_cors": "CORS Başlıklarını Etkinleştir (* - Yerleşik Aktif)",
        "chk_tools": "Uzak İstemci Araç & Ajan Çağrıları (Jinja / Tool Calling / MCP) Aktif",
        "srv_logs": "Canlı llama-server Çıktısı & Yükleme Logları",
        "hf_placeholder": "GGUF Model ara (örn: Qwen3, DeepSeek-R1, Llama-3.3, Gemma-3)...",
        "btn_search": "🔍 Ara",
        "btn_hf_trend": "🔥 Trendler",
        "btn_hf_dl": "⬇️ En Çok İndirilenler",
        "btn_hf_likes": "⭐ En Beğenilenler",
        "btn_hf_new": "🆕 En Yeniler",
        "hf_models_lbl": "Hugging Face GGUF Modelleri (Dosyaları görmek için modele tıklayın):",
        "hf_files_lbl": "Model İçindeki Quant (.gguf) Dosyaları:",
        "dl_active_grp": "İndirme Kuyruğu ve Durumu",
        "dl_empty": "Henüz aktif veya tamamlanmış bir indirme yok.",
        "tel_waiting": "📡 <b>Uzak İstemci Durumu:</b> İstek Bekleniyor...",
        "tel_reading": "📖 <b style='color:#7dcfff;'>Gelen Prompt Okunuyor (Prompt Processing)...</b>",
        "tel_tool": "🔧 <b style='color:#e0af68;'>Uzak İstemci Araç / Ajan İstemi (Tool Call) Çalışıyor...</b>",
        "tel_gen": "✍️ <b style='color:#bb9af7;'>Uzak İstemciye Cevap Üretiliyor...</b>",
        "tel_done": "✅ <b style='color:#9ece6a;'>Yanıt Tamamlandı — Yeni İstek Bekleniyor</b>",
        "btn_abort": "🛑 Üretimi Kes",
        "lbl_no_model": "Model Durumu: Bellekte model yok",
        "btn_load": "🚀 MODELİ YÜKLE (LOAD)",
        "btn_reload": "🔄 YENİDEN YÜKLE (RELOAD)",
        "btn_unload": "⏹ MODELİ BOŞALT (UNLOAD)",
        "btn_drop_cache": "🧹 RAM'İ TEMİZLE (DROP CACHE)",
        "settings_title": "⚙️ <b>Tray AI — Uygulama Ayarları</b>",
        "btn_back_main": "⬅️ Ana Ekrana Dön",
        "set_grp_lang": "Dil ve Görünüm (Language & Appearance)",
        "lbl_ui_lang": "Arayüz Dili:",
        "lang_auto": "Sistem Diline Göre Otomatik (Auto)",
        "set_grp_sys": "Sistem Entegrasyonu & Başlangıç",
        "chk_autostart": "Bilgisayar açıldığında Tray AI'ı sistem tepsisinde otomatik başlat",
        "btn_install_desktop": "🖥️ Uygulama Menüsüne Simgeyi Yeniden Kaydet (.desktop)",
        "set_grp_hf": "Hugging Face API Ayarları",
        "lbl_hf_token": "HF Erişim Tokenı (Gated modeller ve yüksek hız için isteğe bağlı):",
        "tray_toggle": "Pencereyi Göster / Gizle",
        "tray_settings": "⚙️ Ayarlar",
        "tray_exit": "Uygulamadan Çık",
        "pwd_title": "Sistem Parolası Gerekli (sudo)",
        "pwd_prompt": "Sistem RAM önbelleğini (pagecache/dentries) tamamen boşaltmak için\nlütfen kullanıcı (sudo) parolanızı girin:",
        "ram_freed_title": "RAM Önbelleği Temizlendi",
        "ram_freed_msg": "✅ Sistem RAM önbelleği başarıyla boşaltıldı!\nÖnceki Kullanım: {before} GB\nŞu Anki Kullanım: {after} GB\nKazanılan Net Bellek: {diff} GB",
        "ram_err_msg": "❌ Parola hatalı veya yetki verilemedi!"
    },
    "en": {
        "drag_hint": "(Drag here to move)",
        "srv_wait_model": "● Server Active (Waiting for Model)",
        "srv_loading": "● Loading Model...",
        "srv_ready": "● Model Loaded & Ready",
        "srv_stopped": "● Server Stopped",
        "srv_unloaded": "● Server Active (Model Unloaded)",
        "srv_error": "● Error Occurred",
        "tab_models": "Models",
        "tab_config": "Model Settings",
        "tab_hw": "Hardware",
        "tab_server": "Server",
        "tab_hf": "Hugging Face",
        "tab_dl": "Downloads",
        "btn_pick_dir": "📁 Select Folder",
        "btn_rescan": "🔄 Rescan Models",
        "lbl_no_folder": "Not Selected",
        "lbl_engine": "<b>Inference Engine:</b>",
        "lbl_no_meta": "No Model Selected — Waiting for metadata...",
        "grp_ctx": "1. Context & GPU Offload",
        "lbl_ctx": "Context Length (-c):",
        "lbl_ngl": "GPU Offload Layers (-ngl):",
        "grp_kv": "2. K Cache / V Cache Quantization & Memory",
        "chk_kv_gpu": "Offload KV Cache to GPU",
        "chk_mmap": "Use mmap()",
        "chk_mlock": "Use mlock() (Keep in RAM)",
        "grp_batch": "3. CPU Threads, Batch Size & RoPE Frequency",
        "lbl_parallel": "Parallel Slots (-np):",
        "grp_spec": "4. Reasoning Effort & Speculative Decoding (MTP / Draft)",
        "lbl_effort": "Reasoning Effort:",
        "eff_items": ["Disabled", "Low", "Medium", "High", "Custom Budget"],
        "lbl_custom_budget": "Custom Budget:",
        "chk_mtp_ supported": "Enable MTP (Multi-Token Prediction) Layers (Supported)",
        "chk_mtp_none": "MTP Not Supported by Model",
        "chk_draft": "Draft Model:",
        "btn_pick_draft": "Select Model...",
        "grp_samp": "5. Samplers (Temperature, Top-K/P, Min-P, Penalties, Seed)",
        "lbl_temp": "Temperature:",
        "lbl_seed": "Seed:",
        "hw_cpu_ok": "<b>Processor (CPU)</b> <span style='color:#9ece6a;'>✓ Compatible</span>",
        "hw_isa": "Instruction Sets:",
        "hw_sys_ram": "<b>System RAM:</b>",
        "hw_tot_vram": "<b>Total VRAM:</b>",
        "hw_gpus": "Detected GPU Hardware",
        "hw_split": "Multi-GPU Split Strategy:",
        "hw_split_items": ["Split Evenly / Layer Split", "Row Split", "Single GPU (First Active Device Only)"],
        "hw_mon": "Live Resource Monitor",
        "srv_mgmt": "Server Service Management",
        "srv_state_on": "🟢 <b>Server Service: ACTIVE</b>",
        "srv_state_off": "🔴 <b>Server Service: STOPPED</b>",
        "btn_srv_stop": "Stop Server",
        "btn_srv_start": "Start Server",
        "srv_net_grp": "Network, IP, Port & Agent (MCP/Tool) Configuration",
        "lbl_port": "Server Port:",
        "btn_copy_api": "📋 Copy API URL",
        "chk_lan": "Expose on Local Network (0.0.0.0 - Allow LAN clients)",
        "chk_cors": "Enable CORS Headers (* - Built-in Active)",
        "chk_tools": "Enable Remote Client Tool & Agent Calls (Jinja / Tool Calling / MCP)",
        "srv_logs": "Live llama-server Output & Loading Logs",
        "hf_placeholder": "Search GGUF Models (e.g. Qwen3, DeepSeek-R1, Llama-3.3, Gemma-3)...",
        "btn_search": "🔍 Search",
        "btn_hf_trend": "🔥 Trending",
        "btn_hf_dl": "⬇️ Most Downloaded",
        "btn_hf_likes": "⭐ Most Liked",
        "btn_hf_new": "🆕 Recently Updated",
        "hf_models_lbl": "Hugging Face GGUF Models (Click a model to list quant files):",
        "hf_files_lbl": "Available Quant (.gguf) Files in Repository:",
        "dl_active_grp": "Download Queue & Status",
        "dl_empty": "No active or completed downloads yet.",
        "tel_waiting": "📡 <b>Remote Client Status:</b> Waiting for request...",
        "tel_reading": "📖 <b style='color:#7dcfff;'>Reading Incoming Prompt (Prompt Processing)...</b>",
        "tel_tool": "🔧 <b style='color:#e0af68;'>Remote Client Tool / Agent Call Running...</b>",
        "tel_gen": "✍️ <b style='color:#bb9af7;'>Generating Response to Remote Client...</b>",
        "tel_done": "✅ <b style='color:#9ece6a;'>Response Completed — Waiting for Next Request</b>",
        "btn_abort": "🛑 Abort Gen",
        "lbl_no_model": "Model Status: No model loaded in memory",
        "btn_load": "🚀 LOAD MODEL",
        "btn_reload": "🔄 RELOAD MODEL",
        "btn_unload": "⏹ UNLOAD MODEL",
        "btn_drop_cache": "🧹 CLEAR RAM (DROP CACHE)",
        "settings_title": "⚙️ <b>Tray AI — Application Settings</b>",
        "btn_back_main": "⬅️ Back to Main View",
        "set_grp_lang": "Language & Appearance",
        "lbl_ui_lang": "Interface Language:",
        "lang_auto": "Automatic by System Locale (Auto)",
        "set_grp_sys": "System Integration & Startup",
        "chk_autostart": "Automatically start Tray AI in system tray on login",
        "btn_install_desktop": "🖥️ Re-register Application Menu Icon (.desktop)",
        "set_grp_hf": "Hugging Face API Settings",
        "lbl_hf_token": "HF Access Token (Optional, for gated models & higher rate limits):",
        "tray_toggle": "Show / Hide Window",
        "tray_settings": "⚙️ Settings",
        "tray_exit": "Quit Application",
        "pwd_title": "System Password Required (sudo)",
        "pwd_prompt": "To completely flush system RAM cache (pagecache/dentries),\nplease enter your sudo password:",
        "ram_freed_title": "RAM Cache Cleared",
        "ram_freed_msg": "✅ System RAM cache successfully flushed!\nPrevious Usage: {before} GB\nCurrent Usage: {after} GB\nNet Memory Freed: {diff} GB",
        "ram_err_msg": "❌ Incorrect password or permission denied!"
    }
}

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



class MetadataInspectorDialog(QDialog):
    def __init__(self, parent, model_info):
        super().__init__(parent)
        self.setWindowTitle(f"🔍 GGUF Metadata & Mimari Müfettişi — {model_info.get('filename', '')}")
        self.resize(680, 620)
        self.setStyleSheet(DARK_STYLE)

        layout = QVBoxLayout(self)
        extra = model_info.get("extra_meta", {})

        # Üst Özet Kartı
        moe_str = f"{extra.get('expert_used_count', 0)} / {extra.get('expert_count', 0)} Aktif Uzman (MoE)" if extra.get("expert_count", 0) > 0 else "Dense (Standart Yoğun Model)"
        summary = QLabel(
            f"<b>Model Adı:</b> {extra.get('general_name') or model_info['filename']}<br>"
            f"<b>Mimari:</b> <span style='color:#7dcfff;'>{model_info['arch'].upper()}</span>  |  "
            f"<b>Tip:</b> <span style='color:#bb9af7;'>{moe_str}</span>  |  "
            f"<b>Tensor Sayısı:</b> {extra.get('tensor_count', 0)}<br>"
            f"<b>Katman (Blocks):</b> {model_info['total_layers']}  |  "
            f"<b>Embedding:</b> {extra.get('embed_length', 0)}  |  "
            f"<b>FFN Boyutu:</b> {extra.get('feed_forward_length', 0)}<br>"
            f"<b>Attention Heads (Q / KV):</b> {extra.get('head_count', 0)} / {extra.get('head_count_kv', 0)}  |  "
            f"<b>Head Boyutu (K/V):</b> {extra.get('key_length', 128)} / {extra.get('value_length', 128)}<br>"
            f"<b>RoPE Base / Scale:</b> {extra.get('rope_freq_base', 10000)} / {extra.get('rope_scale', 1.0)} ({extra.get('rope_scaling_type', 'none')})  |  "
            f"<b>BOS / EOS Token ID:</b> {extra.get('bos_token_id', -1)} / {extra.get('eos_token_id', -1)}"
        )
        summary.setWordWrap(True)
        summary.setStyleSheet("background: #1f2335; border: 1px solid #3b4261; padding: 10px; border-radius: 6px; font-size: 12px;")
        layout.addWidget(summary)

        tabs = QTabWidget()
        
        # Sekme 1: Tüm GGUF Anahtar-Değer Tablosu
        tab_kv = QWidget()
        v_kv = QVBoxLayout(tab_kv)
        search_input = QLineEdit()
        search_input.setPlaceholderText("🔎 Metadata anahtarı veya değeri ara (örn: rope, attention, tokenizer)...")
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

        # Sekme 2: Gömülü Jinja Chat Template
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
                if file.lower().endswith(".gguf"):
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
        self.resize(640, 880)
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

        # =========================================================================
        # ÜST BAŞLIK ÇUBUĞU (Ayarlar ⚙️ Butonu Dahil)
        # =========================================================================
        top_bar = QHBoxLayout()
        self.lbl_title = QLabel()
        self.lbl_title.setStyleSheet("font-size: 15px; color: #7aa2f7;")
        self.status_lbl = QLabel()
        self.status_lbl.setStyleSheet("color: #7dcfff; font-weight: bold;")
        
        self.btn_settings = QPushButton("⚙️")
        self.btn_settings.setFixedSize(30, 26)
        self.btn_settings.setToolTip("Uygulama Ayarları / Application Settings")
        self.btn_settings.clicked.connect(self.toggle_settings_view)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(26, 26)
        btn_close.clicked.connect(self.hide)

        top_bar.addWidget(self.lbl_title)
        top_bar.addStretch()
        top_bar.addWidget(self.status_lbl)
        top_bar.addWidget(self.btn_settings)
        top_bar.addWidget(btn_close)
        self.main_layout.addLayout(top_bar)

        # =========================================================================
        # ANA GÖRÜNÜM İLE AYARLAR GÖRÜNÜMÜ ARASINDA GEÇİŞ (QStackedWidget)
        # =========================================================================
        self.view_stack = QStackedWidget()
        self.main_layout.addWidget(self.view_stack, 1)

        # Sayfa 0: Ana Sekmeler
        self.tabs = QTabWidget()
        self.view_stack.addWidget(self.tabs)

        self.init_tab_models()
        self.init_tab_config()
        self.init_tab_hardware()
        self.init_tab_server()
        self.init_tab_hf()
        self.init_tab_downloads()

        # Sayfa 1: Uygulama Ayarları Sayfası
        self.init_settings_page()

        # =========================================================================
        # CANLI TELEMETRİ PANELİ
        # =========================================================================
        telemetry_frame = QFrame()
        telemetry_frame.setStyleSheet("background: #1a1b26; border: 1px solid #3b4261; border-radius: 6px; padding: 6px;")
        v_tel = QVBoxLayout(telemetry_frame)
        v_tel.setContentsMargins(8, 5, 8, 5)
        v_tel.setSpacing(4)

        h_tel_top = QHBoxLayout()
        self.lbl_tel_phase = QLabel()
        self.lbl_tel_phase.setStyleSheet("color: #a9b1d6; font-size: 12px;")
        self.lbl_tel_speed = QLabel("⚡ Hız: 0.0 t/s")
        self.lbl_tel_speed.setStyleSheet("color: #73daca; font-weight: bold; font-size: 12px;")
        
        self.btn_abort_gen = QPushButton("🛑")
        self.btn_abort_gen.setFixedHeight(22)
        self.btn_abort_gen.setStyleSheet("background: #414868; color: #f7768e; font-size: 11px; padding: 2px 6px;")
        self.btn_abort_gen.clicked.connect(self.abort_current_generation)

        h_tel_top.addWidget(self.lbl_tel_phase, 1)
        h_tel_top.addWidget(self.lbl_tel_speed)
        h_tel_top.addWidget(self.btn_abort_gen)
        v_tel.addLayout(h_tel_top)

        h_tel_mid = QHBoxLayout()
        self.lbl_prompt_read = QLabel("📖 Prompt Read: %0")
        self.lbl_prompt_read.setStyleSheet("color: #7dcfff; font-weight: bold; font-size: 12px;")
        self.lbl_token_counter = QLabel("🔢 Token: 0")
        self.lbl_token_counter.setStyleSheet("color: #bb9af7; font-weight: bold; font-size: 13px;")
        self.lbl_ctx_usage = QLabel("📦 Ctx: 0 / 0")
        self.lbl_ctx_usage.setStyleSheet("color: #e0af68; font-size: 12px;")

        h_tel_mid.addWidget(self.lbl_prompt_read)
        h_tel_mid.addStretch()
        h_tel_mid.addWidget(self.lbl_token_counter)
        h_tel_mid.addStretch()
        h_tel_mid.addWidget(self.lbl_ctx_usage)
        v_tel.addLayout(h_tel_mid)

        self.bar_prompt_activity = QProgressBar()
        self.bar_prompt_activity.setRange(0, 100)
        self.bar_prompt_activity.setValue(0)
        self.bar_prompt_activity.setFixedHeight(8)
        self.bar_prompt_activity.setTextVisible(False)
        self.bar_prompt_activity.setStyleSheet("QProgressBar { background: #24283b; border-radius: 4px; } QProgressBar::chunk { background: #bb9af7; border-radius: 4px; }")
        v_tel.addWidget(self.bar_prompt_activity)

        self.main_layout.addWidget(telemetry_frame)

        # =========================================================================
        # ALT MODEL YÜKLEME, BOŞALTMA VE RAM TEMİZLEME PANELİ
        # =========================================================================
        load_frame = QFrame()
        load_frame.setStyleSheet("background: #16161e; border: 1px solid #292e42; border-radius: 6px; padding: 6px;")
        v_load = QVBoxLayout(load_frame)
        v_load.setContentsMargins(6, 5, 6, 5)
        v_load.setSpacing(5)

        self.lbl_load_stage = QLabel()
        self.lbl_load_stage.setStyleSheet("font-size: 12px; color: #a9b1d6;")
        v_load.addWidget(self.lbl_load_stage)

        self.load_progress_bar = QProgressBar()
        self.load_progress_bar.setRange(0, 100)
        self.load_progress_bar.setValue(0)
        self.load_progress_bar.setFixedHeight(14)
        v_load.addWidget(self.load_progress_bar)

        h_btns = QHBoxLayout()
        h_btns.setSpacing(6)
        self.btn_load_model = QPushButton()
        self.btn_load_model.setMinimumHeight(40)
        self.btn_load_model.setStyleSheet("background-color: #9ece6a; color: #15161e; font-size: 12px; font-weight: bold; border-radius: 6px; padding: 6px 10px;")
        self.btn_load_model.clicked.connect(self.load_selected_model)

        self.btn_unload_model = QPushButton()
        self.btn_unload_model.setMinimumHeight(40)
        self.btn_unload_model.setStyleSheet("background-color: #f7768e; color: #15161e; font-size: 12px; font-weight: bold; border-radius: 6px; padding: 6px 10px;")
        self.btn_unload_model.setEnabled(False)
        self.btn_unload_model.clicked.connect(self.unload_current_model)

        self.btn_drop_cache = QPushButton()
        self.btn_drop_cache.setMinimumHeight(40)
        self.btn_drop_cache.setStyleSheet("background-color: #7aa2f7; color: #15161e; font-size: 11px; font-weight: bold; border-radius: 6px; padding: 6px 8px;")
        self.btn_drop_cache.setEnabled(False) # Model boşaltıldıktan sonra aktif olur!
        self.btn_drop_cache.clicked.connect(self.flush_system_ram_cache)

        h_btns.addWidget(self.btn_load_model, 3)
        h_btns.addWidget(self.btn_unload_model, 2)
        h_btns.addWidget(self.btn_drop_cache, 2)
        v_load.addLayout(h_btns)

        self.main_layout.addWidget(load_frame)

        # Kaynak izleyici ve Telemetri
        self.res_timer = QTimer(self)
        self.res_timer.timeout.connect(self.update_resource_monitor)
        self.res_timer.start(2000)

        self.poller = TelemetryPoller(port=int(self.cfg.get("port", 8080)))
        self.poller.health_ready.connect(self.on_health_confirmed_ready)
        self.poller.loading_tick.connect(self.on_health_loading_tick)
        self.poller.telemetry_update.connect(self.on_live_telemetry)
        self.poller.start()

        # Dil metinlerini uygula
        self.apply_language()

        # Kayıtlı klasörü yükle
        last_dir = self.cfg.get("last_folder", "")
        if last_dir and os.path.isdir(last_dir):
            self.lbl_folder.setText(f".../{os.path.basename(last_dir)}")
            self.load_from_sqlite_instant(last_dir)

        # İlk açılışta Hugging Face Trend Modelleri otomatik listele
        QTimer.singleShot(600, lambda: self.fetch_hf_models(mode="trending"))

    def _resolve_language(self, lang_setting):
        if lang_setting in ("tr", "en"):
            return lang_setting
        sys_loc = QLocale.system().name().lower()
        return "tr" if sys_loc.startswith("tr") else "en"

    def t(self, key):
        return I18N.get(self.current_lang, I18N["en"]).get(key, key)

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

    # =========================================================================
    # UYGULAMA AYARLARI SAYFASI (Dil, Autostart, HF Token, Simge Kaydı)
    # =========================================================================
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

        # =====================================================================
        # LM STUDIO TARZI RUNTIME & ENGINES GÜNCELLEME MERKEZİ
        # =====================================================================
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

        # TurboQuant Özel Git Deposu / Yerel Klasör Yolu Ayarı
        turbo_src_frame = QFrame()
        turbo_src_frame.setStyleSheet("background: #1a1b26; border: 1px dashed #3b4261; border-radius: 5px; padding: 4px;")
        h_tsrc = QHBoxLayout(turbo_src_frame)
        h_tsrc.setContentsMargins(6, 4, 6, 4)
        h_tsrc.addWidget(QLabel("<b>TurboQuant Repo / Klasör:</b>"))
        self.input_turbo_repo = QLineEdit()
        self.input_turbo_repo.setPlaceholderText("Git URL veya Yerel Klasör (örn: https://github.com/... veya /home/anonymous/...)")
        self.input_turbo_repo.setText(self.cfg.get("turbo_repo", "https://github.com/ggml-org/llama.cpp.git"))
        self.input_turbo_repo.textChanged.connect(self.save_turbo_repo_cfg)
        h_tsrc.addWidget(self.input_turbo_repo, 2)

        h_tsrc.addWidget(QLabel("Dal (Branch):"))
        self.input_turbo_branch = QLineEdit()
        self.input_turbo_branch.setPlaceholderText("master / turboquant")
        self.input_turbo_branch.setFixedWidth(110)
        self.input_turbo_branch.setText(self.cfg.get("turbo_branch", ""))
        self.input_turbo_branch.textChanged.connect(self.save_turbo_repo_cfg)
        h_tsrc.addWidget(self.input_turbo_branch)
        v_rt.addWidget(turbo_src_frame)

        # Motor Kartları
        self.rt_cards_layout = QVBoxLayout()
        v_rt.addLayout(self.rt_cards_layout)

        # Güncelleme İlerleme Çubuğu
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

        # 1. Dil Seçimi
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

        # 2. Sistem Entegrasyonu (Autostart & .desktop)
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

        # 3. Hugging Face Token
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

        # İlk kartları oluştur ve otomatik kontrol açıksa denetle
        self.populate_runtime_cards({
            "local_main": "Kontrol ediliyor...",
            "local_turbo": "Kontrol ediliyor...",
            "latest_tag": "...",
            "assets": {},
            "has_vulkan": True,
            "has_rocm": os.path.exists("/opt/rocm"),
            "has_cuda": False
        })
        if self.cfg.get("auto_update_engine", True):
            QTimer.singleShot(1200, self.check_engine_updates)

    def save_turbo_repo_cfg(self):
        self.cfg["turbo_repo"] = self.input_turbo_repo.text().strip()
        self.cfg["turbo_branch"] = self.input_turbo_branch.text().strip()
        save_json(CONFIG_FILE, self.cfg)

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
                "key": "turboquant",
                "title": "TurboQuant llama.cpp (Linux)",
                "desc": "High-speed quantized inference engine (llama-server-turboquant)",
                "local_ver": info.get("local_turbo", ""),
                "compat": True
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

        t_repo = self.input_turbo_repo.text().strip() if hasattr(self, "input_turbo_repo") else "https://github.com/ggml-org/llama.cpp.git"
        t_branch = self.input_turbo_branch.text().strip() if hasattr(self, "input_turbo_branch") else ""
        self.eng_updater = EngineUpdateWorker(
            engines_dir=USER_ENGINES_DIR,
            target_type=target_key,
            mode=mode,
            asset_url=asset_url,
            turbo_repo=t_repo,
            turbo_branch=t_branch
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
        self.apply_language()

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

    # =========================================================================
    # RAM ÖNBELLEĞİNİ BOŞALT (sudo sync; echo 3 | sudo tee /proc/sys/vm/drop_caches)
    # =========================================================================
    def flush_system_ram_cache(self):
        # Önce eğer arkada kalmış llama-server süreci varsa temizle
        if self.server_mgr.is_running():
            self.server_mgr.stop_model()

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
            # -k ile sudo önbelleğini sıfırla ki şifreyi kesin olarak stdin'den okusun ve 3'ü drop_caches'e yazsın
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
            # llama-server'da aktif üretimi kesmek için hızlı yeniden başlatma veya slot cancel
            self.load_selected_model()

    # =========================================================================
    # SEKMELERİN KURULUMU
    # =========================================================================
    def init_tab_models(self):
        tab = QWidget()
        l = QVBoxLayout(tab)
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
        l.addLayout(top_btn)

        self.list_models = QListWidget()
        self.list_models.setWordWrap(True)
        self.list_models.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_models.itemClicked.connect(self.on_model_selected)
        l.addWidget(self.list_models)
        self.tabs.addTab(tab, "Modeller")

    def init_tab_config(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tab = QWidget()
        l = QVBoxLayout(tab)
        l.setSpacing(10)

        motor_box = QHBoxLayout()
        self.lbl_engine_title = QLabel()
        self.cb_engine = QComboBox()
        self.cb_engine.addItems(["llama-server", "llama-server-turboquant"])
        motor_box.addWidget(self.lbl_engine_title)
        motor_box.addWidget(self.cb_engine)
        l.addLayout(motor_box)

        self.lbl_model_meta_summary = QLabel()
        self.lbl_model_meta_summary.setWordWrap(True)
        self.lbl_model_meta_summary.setStyleSheet("background: #1f2335; color: #7dcfff; padding: 8px; border-radius: 5px; font-size: 12px;")
        l.addWidget(self.lbl_model_meta_summary)

        # Hızlı Aksiyon Barı: Metadata Müfettişi + Otomatik Donanım Optimizasyonu
        h_quick_actions = QHBoxLayout()
        self.btn_inspect_meta = QPushButton("🔍 GGUF Metadata & Şablon Müfettişi")
        self.btn_inspect_meta.setStyleSheet("background: #3b4261; color: #7dcfff; font-weight: bold;")
        self.btn_inspect_meta.clicked.connect(self.open_metadata_inspector)

        self.btn_autotune = QPushButton("⚡ Donanıma Göre Otomatik Ayarla (Auto-Tune)")
        self.btn_autotune.setStyleSheet("background: #3b4261; color: #9ece6a; font-weight: bold;")
        self.btn_autotune.clicked.connect(self.autotune_for_hardware)
        h_quick_actions.addWidget(self.btn_inspect_meta, 1)
        h_quick_actions.addWidget(self.btn_autotune, 1)
        l.addLayout(h_quick_actions)

        # Canlı Bellek (VRAM + RAM + KV Cache) Tahmincisi Kartı
        mem_est_frame = QFrame()
        mem_est_frame.setStyleSheet("background: #1f2335; border: 1px solid #3b4261; border-radius: 6px; padding: 6px;")
        v_est = QVBoxLayout(mem_est_frame)
        v_est.setContentsMargins(6, 4, 6, 4)
        self.lbl_mem_estimate = QLabel("💾 <b>Tahmini Bellek Tüketimi:</b> Model seçildiğinde hesaplanır...")
        self.lbl_mem_estimate.setWordWrap(True)
        self.lbl_mem_estimate.setStyleSheet("font-size: 12px; color: #e0af68;")
        self.bar_mem_estimate = QProgressBar()
        self.bar_mem_estimate.setRange(0, 100)
        self.bar_mem_estimate.setValue(0)
        self.bar_mem_estimate.setFixedHeight(10)
        v_est.addWidget(self.lbl_mem_estimate)
        v_est.addWidget(self.bar_mem_estimate)
        l.addWidget(mem_est_frame)

        # 1. Context ve GPU Offload
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

        # 2. K Cache ve V Cache & Flash Attention
        self.grp_kv = QGroupBox()
        grid_kv = QGridLayout(self.grp_kv)
        grid_kv.addWidget(QLabel("K Cache (-ctk):"), 0, 0)
        self.cb_cache_k = QComboBox()
        self.cb_cache_k.addItems(["f16", "bf16", "q8_0", "q5_1", "q5_0", "q4_1", "q4_0", "iq4_nl", "turbo4", "turbo3", "tq3_0", "tq2_0"])
        grid_kv.addWidget(self.cb_cache_k, 0, 1)

        grid_kv.addWidget(QLabel("V Cache (-ctv):"), 0, 2)
        self.cb_cache_v = QComboBox()
        self.cb_cache_v.addItems(["f16", "bf16", "q8_0", "q5_1", "q5_0", "q4_1", "q4_0", "iq4_nl", "turbo4", "turbo3", "tq3_0", "tq2_0"])
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
        l.addWidget(self.grp_kv)

        # 3. CPU Threads, Batch & RoPE
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

        # 4. Düşünce & Spekülatif Çözme
        self.grp_spec = QGroupBox()
        v_spec = QVBoxLayout(self.grp_spec)
        h_effort = QHBoxLayout()
        self.lbl_effort = QLabel()
        self.cb_thinking_effort = QComboBox()
        self.cb_thinking_effort.addItems(self.t("eff_items"))
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
        self.chk_mtp.setEnabled(False)
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

        # 5. Samplers
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

        # 6. Gelişmiş Yaratıcılık & Tekrar Önleyici Örnekleyiciler (DRY, XTC, Dynatemp, YaRN)
        self.grp_adv_samp = QGroupBox("6. Gelişmiş Samplers (DRY, XTC, Dynamic Temp, YaRN & MoE)")
        grid_as = QGridLayout(self.grp_adv_samp)

        grid_as.addWidget(QLabel("DRY Multiplier:"), 0, 0)
        self.spin_dry_mult = QDoubleSpinBox()
        self.spin_dry_mult.setRange(0.0, 5.0)
        self.spin_dry_mult.setSingleStep(0.1)
        self.spin_dry_mult.setValue(0.0) # 0.8 önerilir
        self.spin_dry_mult.setToolTip("Tekrarları önleyen modern DRY çarpanı (Önerilen: 0.8, Kapalı: 0.0)")
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
        grid_as.addWidget(self.cb_rope_scaling, 3, 1)

        grid_as.addWidget(QLabel("YaRN Ext Factor:"), 3, 2)
        self.spin_yarn_ext = QDoubleSpinBox()
        self.spin_yarn_ext.setRange(-1.0, 16.0)
        self.spin_yarn_ext.setSingleStep(0.5)
        self.spin_yarn_ext.setValue(-1.0)
        grid_as.addWidget(self.spin_yarn_ext, 3, 3)
        l.addWidget(self.grp_adv_samp)

        # 7. Chat Template Override & CLI Komut Önizleme
        self.grp_cli = QGroupBox("7. Chat Template Override & Ekstra CLI Parametreleri")
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

        # Canlı bellek hesaplamasını tetikleyen sinyaller
        self.spin_ctx.valueChanged.connect(self.recalculate_memory_estimate)
        self.spin_ngl.valueChanged.connect(self.recalculate_memory_estimate)
        self.cb_cache_k.currentIndexChanged.connect(self.recalculate_memory_estimate)
        self.cb_cache_v.currentIndexChanged.connect(self.recalculate_memory_estimate)

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

        saved_gpu_states = self.cfg.get("enabled_gpus", {})
        for g in self.hw_info["gpus"]:
            dev_id = str(g["id"])
            card_row = QFrame()
            card_row.setStyleSheet("background: #24283b; border: 1px solid #3b4261; border-radius: 6px; padding: 6px;")
            h_row = QHBoxLayout(card_row)

            lbl_info = QLabel(
                f"<b>{g['name']}</b><br>"
                f"<span style='color:#7aa2f7; font-size:12px;'>VRAM: {g['vram_gb']} GB • {g['backend']} • deviceId: {g['id']}</span>"
            )
            lbl_info.setWordWrap(True)
            
            btn_toggle = QPushButton()
            btn_toggle.setCheckable(True)
            btn_toggle.setFixedSize(95, 30)
            is_on = saved_gpu_states.get(dev_id, True)
            btn_toggle.setChecked(is_on)
            self._update_gpu_btn_style(btn_toggle, is_on)
            btn_toggle.toggled.connect(lambda checked, b=btn_toggle, d=dev_id: self._on_gpu_toggled(b, d, checked))

            self.gpu_toggles[g["id"]] = btn_toggle
            h_row.addWidget(lbl_info, 1)
            h_row.addWidget(btn_toggle)
            v_gpus.addWidget(card_row)

        l.addWidget(self.grp_gpus)

        self.grp_mon = QGroupBox()
        h_mon = QHBoxLayout(self.grp_mon)
        self.lbl_mon_ram = QLabel("RAM: 0 GB")
        self.lbl_mon_cpu = QLabel("CPU: %0.0")
        h_mon.addWidget(self.lbl_mon_ram)
        h_mon.addWidget(self.lbl_mon_cpu)
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

    def _on_gpu_toggled(self, btn, dev_id, checked):
        self._update_gpu_btn_style(btn, checked)
        if "enabled_gpus" not in self.cfg:
            self.cfg["enabled_gpus"] = {}
        self.cfg["enabled_gpus"][dev_id] = checked
        save_json(CONFIG_FILE, self.cfg)

    def update_resource_monitor(self):
        if not self.isVisible():
            return
        mem = psutil.virtual_memory()
        used_gb = round(mem.used / (1024**3), 2)
        cpu_pct = psutil.cpu_percent(interval=None)
        self.lbl_mon_ram.setText(f"RAM: <b>{used_gb} / {self.hw_info['ram_gb']} GB</b>")
        self.lbl_mon_cpu.setText(f"CPU: <b>%{cpu_pct}</b>")

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
        self.txt_logs = QPlainTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setStyleSheet("background: #13141c; color: #9ece6a; font-family: monospace; font-size: 11px;")
        v_log.addWidget(self.txt_logs)
        l.addWidget(self.grp_srv_logs, 1)

        self.tabs.addTab(tab, "Sunucu")

    def copy_endpoint_url(self):
        port = self.spin_port.value()
        ip = self.local_ip if self.chk_lan.isChecked() else "127.0.0.1"
        url = f"http://{ip}:{port}/v1"
        QApplication.clipboard().setText(url)
        self.status_lbl.setText("📋 API URL Copied!")

    def update_endpoint_display(self):
        port = self.spin_port.value()
        self.cfg["port"] = port
        save_json(CONFIG_FILE, self.cfg)
        if hasattr(self, "poller"):
            self.poller.set_port(port)
        if self.chk_lan.isChecked():
            self.lbl_ip.setText(
                f"🌐 <b>LAN Endpoint:</b> http://{self.local_ip}:{port}/v1<br>"
                f"💻 <b>Localhost:</b> http://127.0.0.1:{port}/v1"
            )
        else:
            self.lbl_ip.setText(f"🔒 <b>Localhost Only:</b> http://127.0.0.1:{port}/v1")

    def toggle_server_service(self):
        if self.server_service_enabled:
            self.server_service_enabled = False
            if self.server_mgr.is_running():
                self.unload_current_model()
            self.lbl_srv_state.setText(self.t("srv_state_off"))
            self.btn_srv_toggle.setText(self.t("btn_srv_start"))
            self.status_lbl.setText(self.t("srv_stopped"))
            self.status_lbl.setStyleSheet("color: #f7768e; font-weight: bold;")
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

    # =========================================================================
    # HUGGING FACE KEŞİF, TRENDLER VE QUANT DOSYA SEÇİMİ SEKMESİ
    # =========================================================================
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

    # =========================================================================
    # İNDİRİLENLER SEKMESİ (Duraklatma / Devam / İptal)
    # =========================================================================
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

        # İndirilenler sekmesine geç
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
        # İnen modeli otomatik analiz edip Modeller sekmesine ekle
        folder = self.cfg.get("last_folder", "")
        if folder and os.path.isdir(folder):
            self.load_from_sqlite_instant(folder)

    def on_dl_error(self, task_id, err_msg):
        if task_id in self.active_downloads:
            _, w = self.active_downloads[task_id]
            w.lbl_state.setText(f"❌ Hata: {err_msg}")
            w.lbl_state.setStyleSheet("color: #f7768e;")

    # =========================================================================
    # DİL UYGULAMA FONKSİYONU
    # =========================================================================
    def apply_language(self):
        self.lbl_title.setText(f"⚡ <b>Tray AI</b> <span style='font-size:11px; color:#565f89;'>{self.t('drag_hint')}</span>")
        if not self.server_mgr.is_running():
            self.status_lbl.setText(self.t("srv_wait_model") if self.server_service_enabled else self.t("srv_stopped"))
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

        self.btn_select_dir.setText(self.t("btn_pick_dir"))
        self.btn_rescan.setText(self.t("btn_rescan"))
        if not self.cfg.get("last_folder"):
            self.lbl_folder.setText(self.t("lbl_no_folder"))

        self.lbl_engine_title.setText(self.t("lbl_engine"))
        if not self.active_model_info:
            self.lbl_model_meta_summary.setText(self.t("lbl_no_meta"))
        self.grp_ctx.setTitle(self.t("grp_ctx"))
        self.lbl_ctx_title.setText(self.t("lbl_ctx"))
        self.lbl_ngl_title.setText(self.t("lbl_ngl"))
        self.grp_kv.setTitle(self.t("grp_kv"))
        self.chk_offload_kv.setText(self.t("chk_kv_gpu"))
        self.chk_mmap.setText(self.t("chk_mmap"))
        self.chk_mlock.setText(self.t("chk_mlock"))
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

    # =========================================================================
    # MODEL YÖNETİMİ VE SUNUCU ÇALIŞTIRMA
    # =========================================================================
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

        # Tüm katmanları aktif GPU/iGPU'ya ver
        self.slider_ngl.setValue(layers)
        # Bellek kapasitesine göre optimum bağlam ve KV cache seç
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

        status_icon = "✅ Rahat Sığar" if pct < 75 else ("⚠️ Sınırda" if pct < 92 else "❌ Bellek Yetersiz Olabilir")
        self.lbl_mem_estimate.setText(
            f"💾 <b>Tahmini Bellek: {est['total_gb']} GB</b> "
            f"(Model: {self.active_model_info['size_gb']} GB + KV Cache: {est['kv_gb']} GB)  —  "
            f"<b>{status_icon} (Sistem: %{pct})</b>"
        )

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
            if os.path.exists(m["path"]):
                self.add_model_item_to_list(m)

        self.scanner_thread = FastScannerThread(folder, self.cache_mgr)
        self.scanner_thread.new_model_found.connect(self.on_bg_model_found)
        self.scanner_thread.start()

    def on_bg_model_found(self, info):
        if info["path"] not in self.loaded_models:
            self.add_model_item_to_list(info)

    def add_model_item_to_list(self, info):
        self.loaded_models[info["path"]] = info
        badges = []
        if info["has_thinking"]: badges.append("🧠")
        if info["has_tools"]: badges.append("🔧")
        if info["has_vision"]: badges.append("👁️")
        if info["has_mtp"]: badges.append("⚡MTP")

        badge_str = f" [{' '.join(badges)}]" if badges else ""
        txt = f"{info['filename']} ({info['size_gb']} GB)\n↳ Layers: {info['total_layers']} | Max Ctx: {info['max_context']} | {info['quant']}{badge_str}"
        item = QListWidgetItem(txt)
        item.setData(Qt.ItemDataRole.UserRole, info["path"])
        self.list_models.addItem(item)

    def on_model_selected(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path or path not in self.loaded_models:
            return

        self.selected_model_path = path
        info = self.loaded_models[path]
        self.active_model_info = info
        extra_m = info.get("extra_meta", {})

        self.lbl_model_meta_summary.setText(
            f"<b>Model:</b> {info['filename']} | <b>Arch:</b> {info['arch']} | "
            f"<b>Layers:</b> {info['total_layers']} | <b>Max Ctx:</b> {info['max_context']} | "
            f"<b>Embed:</b> {extra_m.get('embed_length', 0)} | <b>KV Heads:</b> {extra_m.get('head_count_kv', 0)}"
        )

        layers = info.get("total_layers", 32)
        self.slider_ngl.setRange(0, layers)
        self.spin_ngl.setRange(0, layers)

        max_ctx = info.get("max_context", 4096)
        self.slider_ctx.setRange(512, max_ctx)
        self.spin_ctx.setRange(512, max_ctx)

        # Kayıtlı model özel ayarı varsa yükle, yoksa metadata varsayılanlarını koy
        saved_m_cfg = self.cfg.get("per_model_cfg", {}).get(path, {})
        self.slider_ngl.setValue(min(layers, saved_m_cfg.get("ngl", layers)))
        self.slider_ctx.setValue(min(max_ctx, saved_m_cfg.get("ctx", max_ctx)))

        self.spin_rope_base.setValue(float(extra_m.get("rope_freq_base", 10000.0)))
        self.recalculate_memory_estimate()
        self.spin_rope_scale.setValue(float(extra_m.get("rope_scale", 1.0)))

        if info.get("has_mtp", False):
            self.chk_mtp.setEnabled(True)
            self.chk_mtp.setChecked(True)
            self.chk_mtp.setText(self.t("chk_mtp_ supported"))
        else:
            self.chk_mtp.setEnabled(False)
            self.chk_mtp.setChecked(False)
            self.chk_mtp.setText(self.t("chk_mtp_none"))

        if info.get("has_thinking", False):
            self.cb_thinking_effort.setEnabled(True)
            self.cb_thinking_effort.setCurrentIndex(2)
        else:
            self.cb_thinking_effort.setEnabled(False)
            self.cb_thinking_effort.setCurrentIndex(0)
            self.spin_thinking_tokens.setEnabled(False)

    def load_selected_model(self):
        if not self.server_service_enabled:
            return
        if not self.selected_model_path or not os.path.exists(self.selected_model_path):
            return

        engine = self.cb_engine.currentText()
        ngl = self.spin_ngl.value()
        ctx = self.spin_ctx.value()
        port = self.spin_port.value()
        host = "0.0.0.0" if self.chk_lan.isChecked() else "127.0.0.1"

        # Model başına ayarları kaydet
        if "per_model_cfg" not in self.cfg:
            self.cfg["per_model_cfg"] = {}
        self.cfg["per_model_cfg"][self.selected_model_path] = {"ngl": ngl, "ctx": ctx}
        save_json(CONFIG_FILE, self.cfg)

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

        # Uzak İstemci Araç & Ajan (Tool Calling / MCP) Tam Desteği
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

        if self.cb_thinking_effort.isEnabled():
            eff_idx = self.cb_thinking_effort.currentIndex()
            if eff_idx == 0: extra.extend(["--reasoning-budget", "0"])
            elif eff_idx == 1: extra.extend(["--reasoning-budget", "1024"])
            elif eff_idx == 2: extra.extend(["--reasoning-budget", "4096"])
            elif eff_idx == 3: extra.extend(["--reasoning-budget", "16384"])
            elif eff_idx == 4:
                extra.extend(["--reasoning-budget", str(self.spin_thinking_tokens.value())])

        # Gelişmiş Samplers (DRY, XTC, Dynatemp, Typical-P, RoPE Scaling)
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

        if self.chk_enable_draft.isChecked() and self.selected_draft_path:
            extra.extend(["-md", self.selected_draft_path, "--draft-max", str(self.spin_draft_max.value())])

        self.txt_logs.clear()
        self.poller.set_port(port)
        self.poller.reset_ready()
        self.load_progress_bar.setValue(5)
        self.lbl_load_stage.setText("⏳ RAM / VRAM...")
        self.status_lbl.setText(self.t("srv_loading"))
        self.status_lbl.setStyleSheet("color: #e0af68; font-weight: bold;")
        self.btn_drop_cache.setEnabled(False)
        tray_ref.setIcon(get_tray_icon("loading"))

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
            QMessageBox.critical(self, "Error", str(e))

    def unload_current_model(self):
        self.server_mgr.stop_model()
        self.poller.reset_ready()
        self.load_progress_bar.setValue(0)
        self.bar_prompt_activity.setValue(0)
        self.lbl_load_stage.setText(self.t("lbl_no_model"))
        self.lbl_tel_phase.setText(self.t("tel_waiting"))
        self.lbl_prompt_read.setText("📖 Prompt Read: %0")
        self.lbl_token_counter.setText("🔢 Token: 0")
        self.btn_unload_model.setEnabled(False)
        self.btn_drop_cache.setEnabled(True) # Model boşaltıldı! Şimdi RAM Temizleme butonu AKTİF!
        self.btn_load_model.setText(self.t("btn_load"))
        if self.server_service_enabled:
            self.status_lbl.setText(self.t("srv_unloaded"))
            self.status_lbl.setStyleSheet("color: #7dcfff; font-weight: bold;")
            tray_ref.setIcon(get_tray_icon("ready"))

    def on_server_log(self, line):
        self.txt_logs.appendPlainText(line)

    def on_load_progress(self, pct, stage_text):
        if pct > self.load_progress_bar.value():
            self.load_progress_bar.setValue(pct)
            self.lbl_load_stage.setText(f"⏳ {stage_text} (%{pct})")

    def on_health_loading_tick(self):
        cur = self.load_progress_bar.value()
        if 0 < cur < 95:
            new_val = min(95, cur + 4)
            self.load_progress_bar.setValue(new_val)
            self.lbl_load_stage.setText(f"⏳ RAM/VRAM Offloading... (%{new_val})")

    def on_health_confirmed_ready(self):
        if self.server_mgr.reader_thread:
            self.server_mgr.reader_thread.mark_ready_external()
        else:
            self.on_model_ready()

    def on_model_ready(self):
        self.load_progress_bar.setValue(100)
        m_name = os.path.basename(self.selected_model_path) if self.selected_model_path else "Model"
        self.lbl_load_stage.setText(f"✅ {m_name} (%100)")
        self.lbl_tel_phase.setText(self.t("tel_waiting"))
        self.status_lbl.setText(self.t("srv_ready"))
        self.status_lbl.setStyleSheet("color: #9ece6a; font-weight: bold;")
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

        self.lbl_ctx_usage.setText(f"📦 Ctx: {n_past} / {n_ctx}")

        if is_proc:
            tray_ref.setIcon(get_tray_icon("generating"))
            if phase == "prompt":
                self.remote_tool_active = False
                pct = info["prompt_pct"]
                self.lbl_tel_phase.setText(self.t("tel_reading"))
                self.lbl_prompt_read.setText(f"📖 Prompt Read: %{pct}")
                self.lbl_token_counter.setText("🔢 Token: 0")
                self.bar_prompt_activity.setValue(pct)
                if pp_speed > 0:
                    self.lbl_tel_speed.setText(f"⚡ PP: {pp_speed:.1f} t/s")
            else:
                self.lbl_prompt_read.setText("📖 Prompt Read: %100")
                self.bar_prompt_activity.setValue(100)
                if is_tool:
                    self.lbl_tel_phase.setText(self.t("tel_tool"))
                else:
                    self.lbl_tel_phase.setText(self.t("tel_gen"))
                    self.lbl_token_counter.setText(f"🔢 Token: {tokens_gen}")

                if tg_speed > 0:
                    self.lbl_tel_speed.setText(f"⚡ TG: {tg_speed:.1f} t/s")
        else:
            self.remote_tool_active = False
            tray_ref.setIcon(get_tray_icon("active"))
            self.lbl_tel_phase.setText(self.t("tel_done"))
            if tg_speed > 0:
                self.lbl_tel_speed.setText(f"⚡ {tg_speed:.1f} t/s")

    def on_process_stopped(self, code):
        if self.load_progress_bar.value() < 100 and code != 0:
            self.lbl_load_stage.setText(f"❌ Code: {code} (Check Server Logs)")
            self.status_lbl.setText(self.t("srv_error"))
            self.status_lbl.setStyleSheet("color: #f7768e; font-weight: bold;")
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
        if self.window.server_mgr.is_running():
            self.window.server_mgr.stop_model()
        self.app.quit()

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    runner = MainRunner()
    runner.run()
