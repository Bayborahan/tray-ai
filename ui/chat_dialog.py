import json
import time
import base64
import os
import re
import subprocess
import requests
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QScrollArea, QMessageBox,
    QFileDialog, QFrame, QComboBox, QWidget, QPlainTextEdit,
    QInputDialog, QApplication
)
from PyQt6.QtGui import QPixmap
from ui.styles import DARK_STYLE

PERSONAS = {
    "sysadmin": "Sen doğrudan Linux terminaline bağlı çalışan Otonom bir Sistem Yöneticisi Ajanısın (SysAdmin Copilot). Sistem sorunlarını çözmek, donanım, çekirdek ve servis durumlarını denetlemek için gereken komutları ```bash ... ``` bloğu içinde çalıştır. Asla kullanıcıya 'bu komutları sen çalıştır ve bana getir' deme! Sen komutu verir vermez arayüz bunu terminalde çalıştıracak ve çıktısı sana dönecektir. Komuttan sonra sadece 'Terminal üzerinden durumu kontrol ediyorum:' de ve komutunu ver.",
    "coder": "You are an expert senior software engineer specializing in Linux, C, Python, and system architecture. Provide clean, production-ready code with concise explanations.",
    "general": "You are a helpful, concise, and highly intelligent AI assistant.",
    "reasoning": "You are a deep logical reasoning engine. Think carefully step by step before answering.",
    "concise": "Answer directly and concisely without unnecessary introductory or concluding remarks."
}

class CommandExecWorker(QThread):
    finished_output = pyqtSignal(str, int)

    def __init__(self, command, sudo_pwd=None):
        super().__init__()
        self.command = command
        self.sudo_pwd = sudo_pwd

    def run(self):
        try:
            if self.sudo_pwd:
                proc = subprocess.Popen(
                    ["sudo", "-S", "bash", "-c", self.command],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                out, _ = proc.communicate(input=self.sudo_pwd + "\n", timeout=35)
                ret = proc.returncode
            else:
                proc = subprocess.Popen(
                    ["bash", "-c", self.command],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                out, _ = proc.communicate(timeout=35)
                ret = proc.returncode

            clean_out = out.strip() if out else "[Komut başarıyla çalıştı (Çıktı yok)]"
            self.finished_output.emit(clean_out, ret)
        except subprocess.TimeoutExpired:
            self.finished_output.emit("⚠️ Komut zaman aşımına uğradı (35s) ve durduruldu.", -1)
        except Exception as e:
            self.finished_output.emit(f"❌ Komut çalıştırma hatası: {e}", -1)


class TerminalActionWidget(QFrame):
    def __init__(self, command, chat_dialog_ref, auto_exec=False, parent=None):
        super().__init__(parent)
        self.command = command.strip()
        self.chat_dialog = chat_dialog_ref
        self.is_sudo = "sudo " in self.command or self.command.startswith("sudo")
        self.output_text = ""

        self.setStyleSheet("""
            QFrame#termCard {
                background-color: #0f111a;
                border: 1px solid #292e42;
                border-left: 3px solid #7aa2f7;
                border-radius: 8px;
                margin-top: 6px;
            }
        """)
        self.setObjectName("termCard")

        v = QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(6)

        h_top = QHBoxLayout()
        lbl_head = QLabel("💻 <b>Terminal Önerisi:</b> <code>bash</code>")
        lbl_head.setStyleSheet("color: #7dcfff; font-size: 11px;")
        h_top.addWidget(lbl_head)
        h_top.addStretch()

        if self.is_sudo:
            lbl_sudo = QLabel("🛡️ Sudo İzni Gerekir")
            lbl_sudo.setStyleSheet("""
                background: #3d2f1f;
                color: #ff9e64;
                padding: 1px 6px;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
                border: 1px solid #ff9e64;
            """)
            h_top.addWidget(lbl_sudo)

        v.addLayout(h_top)

        self.lbl_cmd = QLabel(f"$ {self.command}")
        self.lbl_cmd.setWordWrap(True)
        self.lbl_cmd.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl_cmd.setStyleSheet("""
            background: #16161e;
            color: #73daca;
            font-family: 'Ubuntu Mono', monospace;
            font-size: 12px;
            padding: 6px 8px;
            border-radius: 5px;
            border: 1px solid #292e42;
        """)
        v.addWidget(self.lbl_cmd)

        self.txt_term_out = QPlainTextEdit()
        self.txt_term_out.setReadOnly(True)
        self.txt_term_out.setFixedHeight(140)
        self.txt_term_out.setStyleSheet("""
            QPlainTextEdit {
                background-color: #090a10;
                color: #9ece6a;
                font-family: 'Ubuntu Mono', 'Courier New', monospace;
                font-size: 11px;
                border: 1px solid #1a1e2d;
                border-radius: 5px;
                padding: 6px;
            }
        """)
        self.txt_term_out.hide()
        v.addWidget(self.txt_term_out)

        h_btns = QHBoxLayout()
        h_btns.setSpacing(6)

        self.btn_run = QPushButton("⚡ Komutu Çalıştır")
        self.btn_run.setAutoDefault(False)
        self.btn_run.setDefault(False)
        self.btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run.setStyleSheet("""
            QPushButton {
                background: #7aa2f7;
                color: #15161e;
                font-weight: bold;
                font-size: 11px;
                padding: 5px 12px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: #89b4fa;
            }
        """)
        self.btn_run.clicked.connect(self.run_command)
        h_btns.addWidget(self.btn_run)

        self.btn_copy = QPushButton("📋 Kopyala")
        self.btn_copy.setAutoDefault(False)
        self.btn_copy.setDefault(False)
        self.btn_copy.setStyleSheet("background: #1f2335; border: 1px solid #3b4261; font-size: 11px; padding: 5px 10px; border-radius: 5px;")
        self.btn_copy.clicked.connect(lambda: (self.chat_dialog.copy_to_clip(self.command), self.btn_copy.setText("✓ Kopyalandı!"), QTimer.singleShot(1500, lambda: self.btn_copy.setText("📋 Kopyala"))))
        h_btns.addWidget(self.btn_copy)

        self.btn_feed_model = QPushButton("📤 Çıktıyı Modele Gönder (Analiz Et)")
        self.btn_feed_model.setAutoDefault(False)
        self.btn_feed_model.setDefault(False)
        self.btn_feed_model.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_feed_model.setStyleSheet("""
            QPushButton {
                background: #bb9af7;
                color: #15161e;
                font-weight: bold;
                font-size: 11px;
                padding: 5px 12px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: #cbb0f9;
            }
        """)
        self.btn_feed_model.clicked.connect(self.feed_output_to_model)
        self.btn_feed_model.hide()
        h_btns.addWidget(self.btn_feed_model)

        h_btns.addStretch()
        v.addLayout(h_btns)

        destructive_keywords = ["sudo", "rm ", "mkfs", "dd ", "reboot", "shutdown", "poweroff", "kill", "> /dev/"]
        is_safe = not any(k in self.command.lower() for k in destructive_keywords)
        if auto_exec and is_safe:
            QTimer.singleShot(100, self.auto_run_and_feed)

    def auto_run_and_feed(self):
        self.btn_run.setText("⚡ Otonom Çalıştırılıyor...")
        self.btn_run.setEnabled(False)
        self.txt_term_out.show()
        self.txt_term_out.setPlainText("⚡ Otonom Ajan komutu yürütüyor...")

        def _on_done(out, ret):
            self.output_text = out
            self.txt_term_out.setPlainText(out)
            self.btn_run.setText("✅ Tamamlandı" if ret == 0 else "⚠️ Tamamlandı")
            self.btn_feed_model.setText("✓ Otonom İletildi")
            self.btn_feed_model.setEnabled(False)
            self.btn_feed_model.show()
            QTimer.singleShot(400, self.feed_output_to_model)

        self.worker = CommandExecWorker(self.command, None)
        self.worker.finished_output.connect(_on_done)
        self.worker.start()

    def run_command(self):
        sudo_pwd = None
        if self.is_sudo:
            pwd, ok = QInputDialog.getText(
                self,
                "Sudo Parolası Gerekli",
                f"<b>'{self.command}'</b> komutunu root yetkisiyle çalıştırmak için parolanızı girin:",
                QLineEdit.EchoMode.Password
            )
            if not ok or not pwd:
                return
            sudo_pwd = pwd

        self.btn_run.setEnabled(False)
        self.btn_run.setText("⏳ Çalıştırılıyor...")
        self.txt_term_out.show()
        self.txt_term_out.setPlainText("⏳ Komut yürütülüyor, lütfen bekleyin...")

        self.worker = CommandExecWorker(self.command, sudo_pwd)
        self.worker.finished_output.connect(self.on_command_finished)
        self.worker.start()

    def on_command_finished(self, out, ret_code):
        self.output_text = out
        self.txt_term_out.setPlainText(out)
        self.btn_run.setText("✅ Tamamlandı" if ret_code == 0 else "⚠️ Hata İle Bitti")
        self.btn_run.setStyleSheet("background: #24283b; color: #9ece6a; font-size: 11px; font-weight: bold; border-radius: 5px;")
        self.btn_feed_model.show()
        QTimer.singleShot(20, self.chat_dialog.scroll_to_bottom)

    def feed_output_to_model(self):
        if not self.output_text:
            return
        prompt_text = (
            f"💻 Çalıştırılan Komut: `{self.command}`\n\n"
            f"Terminal Çıktısı:\n```text\n{self.output_text[:2500]}\n```\n\n"
            f"Lütfen yukarıdaki terminal çıktısını incele, sonucu analiz et ve bir sonraki adımı açıkla."
        )
        self.btn_feed_model.setEnabled(False)
        self.btn_feed_model.setText("✓ İletildi")
        self.chat_dialog.send_automated_prompt(prompt_text, visible_title=f"💻 '{self.command}' çıktısı analiz ediliyor...")


class UserBubble(QFrame):
    def __init__(self, text, img_path=None, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame#userBubble {
                background-color: #24283b;
                border: 1px solid #3b4261;
                border-radius: 14px;
                border-bottom-right-radius: 3px;
            }
        """)
        self.setObjectName("userBubble")
        self.setMaximumWidth(540)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(5)

        lbl_sender = QLabel("👤 Sen")
        lbl_sender.setStyleSheet("color: #7dcfff; font-weight: bold; font-size: 11px;")
        layout.addWidget(lbl_sender)

        if img_path and os.path.exists(img_path):
            lbl_img = QLabel()
            pix = QPixmap(img_path)
            if not pix.isNull():
                scaled = pix.scaledToWidth(240, Qt.TransformationMode.SmoothTransformation)
                lbl_img.setPixmap(scaled)
                lbl_img.setStyleSheet("border-radius: 6px; margin: 4px 0;")
                layout.addWidget(lbl_img)

        self.lbl_text = QLabel(text)
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl_text.setStyleSheet("color: #c0caf5; font-size: 13px; line-height: 1.4;")
        layout.addWidget(self.lbl_text)


class AssistantBubble(QFrame):
    def __init__(self, model_name, chat_dialog_ref, parent=None):
        super().__init__(parent)
        self.chat_dialog = chat_dialog_ref
        self.setStyleSheet("""
            QFrame#aiBubble {
                background-color: #1f2335;
                border: 1px solid #292e42;
                border-left: 3px solid #bb9af7;
                border-radius: 14px;
                border-bottom-left-radius: 3px;
            }
        """)
        self.setObjectName("aiBubble")
        self.setMaximumWidth(600)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(14, 10, 14, 10)
        self.layout.setSpacing(6)

        lbl_sender = QLabel(f"🤖 {model_name}")
        lbl_sender.setStyleSheet("color: #bb9af7; font-weight: bold; font-size: 12px;")
        self.layout.addWidget(lbl_sender)

        self.thinking_frame = QFrame()
        self.thinking_frame.setStyleSheet("""
            QFrame {
                background-color: #161822;
                border: 1px dashed #414868;
                border-left: 2px solid #e0af68;
                border-radius: 8px;
                padding: 6px;
            }
        """)
        v_think = QVBoxLayout(self.thinking_frame)
        v_think.setContentsMargins(8, 6, 8, 6)
        v_think.setSpacing(4)

        lbl_think_title = QLabel("💭 Düşünce Süreci (Reasoning)")
        lbl_think_title.setStyleSheet("color: #e0af68; font-weight: bold; font-size: 11px;")
        v_think.addWidget(lbl_think_title)

        self.lbl_think_text = QLabel()
        self.lbl_think_text.setWordWrap(True)
        self.lbl_think_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl_think_text.setStyleSheet("color: #7a829e; font-style: italic; font-size: 12px; line-height: 1.35;")
        v_think.addWidget(self.lbl_think_text)
        self.thinking_frame.hide()
        self.layout.addWidget(self.thinking_frame)

        self.lbl_response = QLabel("...")
        self.lbl_response.setWordWrap(True)
        self.lbl_response.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl_response.setStyleSheet("color: #c0caf5; font-size: 13px; line-height: 1.45;")
        self.layout.addWidget(self.lbl_response)

        self.lbl_stats = QLabel()
        self.lbl_stats.setStyleSheet("color: #73daca; font-weight: bold; font-size: 11px; margin-top: 4px;")
        self.lbl_stats.hide()
        self.layout.addWidget(self.lbl_stats)

        self.thinking_buffer = ""
        self.response_buffer = ""
        self.has_term_injected = False

    def append_thinking(self, chunk):
        if not self.thinking_frame.isVisible():
            self.thinking_frame.show()
        self.thinking_buffer += chunk
        self.lbl_think_text.setText(self.thinking_buffer)

    def append_response(self, chunk):
        if self.lbl_response.text() == "...":
            self.response_buffer = ""
        self.response_buffer += chunk
        self.lbl_response.setText(self.response_buffer)

    def finalize_markdown(self, suppress_auto_run=False):
        if self.response_buffer:
            self.lbl_response.setTextFormat(Qt.TextFormat.MarkdownText)
            self.lbl_response.setText(self.response_buffer)

        if not self.has_term_injected:
            self.has_term_injected = True
            bash_matches = re.findall(r"```(?:bash|sh)\s*\n(.*?)```", self.response_buffer, re.DOTALL)
            for raw_cmd in bash_matches:
                clean_c = raw_cmd.strip()
                if clean_c and not clean_c.startswith("#"):
                    auto_flag = False if suppress_auto_run else (getattr(self.chat_dialog, "chk_autopilot", None) and self.chat_dialog.chk_autopilot.isChecked())
                    term_widget = TerminalActionWidget(clean_c, self.chat_dialog, auto_exec=auto_flag)
                    self.layout.addWidget(term_widget)

    def set_stats(self, ttft, speed, tokens):
        self.lbl_stats.setText(f"⚡ TTFT: {ttft*1000:.0f} ms • Hız: {speed:.1f} t/s • Toplam: {tokens} token")
        self.lbl_stats.show()

    def set_error(self, err_msg):
        self.lbl_response.setText(f"❌ Hata: {err_msg}")
        self.lbl_response.setStyleSheet("color: #f7768e; font-size: 12px;")


class ChatStreamWorker(QThread):
    chunk_received = pyqtSignal(str, bool)
    stats_ready = pyqtSignal(float, float, int)
    finished_ok = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, port, model_id, messages):
        super().__init__()
        self.port = port
        self.model_id = model_id
        self.messages = list(messages)
        self._is_aborted = False
        self._resp = None

    def abort(self):
        self._is_aborted = True
        try:
            if self._resp:
                self._resp.close()
        except Exception:
            pass

    def run(self):
        url = f"http://127.0.0.1:{self.port}/v1/chat/completions"
        payload = {
            "model": self.model_id,
            "messages": self.messages,
            "stream": True,
            "temperature": 0.6,
            "stop": ["<|im_end|>", "<end_of_turn>", "<|eot_id|>", "<|endoftext|>", "</s>", "<|turn_end|>", "<turn>"]
        }

        start_time = time.time()
        first_token_time = None
        token_count = 0
        in_thinking_tag = False

        try:
            self._resp = requests.post(url, json=payload, stream=True, timeout=180)
            if self._resp.status_code != 200:
                if not self._is_aborted:
                    self.error_occurred.emit(f"HTTP {self._resp.status_code}: {self._resp.text[:250]}")
                return

            for line in self._resp.iter_lines():
                if self._is_aborted:
                    break
                if not line:
                    continue

                line_str = line.decode("utf-8", errors="replace").strip()
                if line_str.startswith("data: "):
                    data_str = line_str[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk_obj = json.loads(data_str)
                        delta = chunk_obj.get("choices", [{}])[0].get("delta", {})

                        reasoning_part = delta.get("reasoning_content", "") or delta.get("reasoning", "")
                        content_part = delta.get("content", "")
                        now = time.time()

                        if reasoning_part:
                            if first_token_time is None:
                                first_token_time = now
                            token_count += 1
                            if not self._is_aborted:
                                self.chunk_received.emit(reasoning_part, True)

                        if content_part:
                            if first_token_time is None:
                                first_token_time = now
                            token_count += 1

                            if "<think>" in content_part:
                                in_thinking_tag = True
                                content_part = content_part.replace("<think>", "")
                            if "</think>" in content_part:
                                in_thinking_tag = False
                                parts = content_part.split("</think>")
                                if parts[0] and not self._is_aborted:
                                    self.chunk_received.emit(parts[0], True)
                                if len(parts) > 1 and parts[1] and not self._is_aborted:
                                    self.chunk_received.emit(parts[1], False)
                                continue

                            for st in ["<|im_end|>", "<end_of_turn>", "<|eot_id|>", "<|endoftext|>", "</s>", "<|turn_end|>", "<turn>"]:
                                content_part = content_part.replace(st, "")

                            if content_part and not self._is_aborted:
                                self.chunk_received.emit(content_part, in_thinking_tag)

                    except Exception:
                        pass

            end_time = time.time()
            ttft = (first_token_time - start_time) if first_token_time else 0.0
            gen_duration = max(0.01, end_time - (first_token_time or start_time))
            speed = (token_count / gen_duration) if token_count > 0 else 0.0

            if not self._is_aborted:
                self.stats_ready.emit(ttft, speed, token_count)
                self.finished_ok.emit()

        except Exception as e:
            if not self._is_aborted:
                self.error_occurred.emit(str(e))
        finally:
            try:
                if self._resp:
                    self._resp.close()
            except Exception:
                pass


class ChatTesterDialog(QDialog):
    def __init__(self, parent, engine_port, active_model_func):
        super().__init__(parent)
        self.engine_port = engine_port
        self.active_model_func = active_model_func
        self.setWindowTitle("💬 Model Test Sohbeti & Linux Terminal Copilot")
        self.resize(720, 820)
        self.setStyleSheet(DARK_STYLE)
        self.setAcceptDrops(True)

        self.messages = []
        self.worker = None
        self.current_active_bubble = None
        self.current_attached_image = None
        self.is_generating = False
        self._last_start_time = 0.0

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        top_box = QHBoxLayout()
        self.lbl_model_badge = QLabel()
        self.lbl_model_badge.setStyleSheet(
            "background: #1f2335; border: 1px solid #3b4261; border-left: 3px solid #7aa2f7; "
            "padding: 6px 10px; border-radius: 6px; font-size: 12px; color: #7dcfff;"
        )
        top_box.addWidget(self.lbl_model_badge, 1)

        self.btn_export = QPushButton("💾 Dışa Aktar (.md)")
        self.btn_export.setAutoDefault(False)
        self.btn_export.setDefault(False)
        self.btn_export.setFixedHeight(28)
        self.btn_export.setStyleSheet("background: #24283b; border: 1px solid #414868; font-size: 11px;")
        self.btn_export.clicked.connect(self.export_chat_markdown)
        top_box.addWidget(self.btn_export)

        btn_clear = QPushButton("🧹 Temizle")
        btn_clear.setAutoDefault(False)
        btn_clear.setDefault(False)
        btn_clear.setFixedHeight(28)
        btn_clear.setStyleSheet("background: #24283b; border: 1px solid #414868; font-size: 11px;")
        btn_clear.clicked.connect(self.clear_chat)
        top_box.addWidget(btn_clear)
        layout.addLayout(top_box)

        persona_row = QHBoxLayout()
        lbl_p = QLabel("🎭 <b>Sistem Rolü:</b>")
        lbl_p.setStyleSheet("color: #bb9af7; font-size: 11px;")
        self.cb_persona = QComboBox()
        self.cb_persona.addItem("🐧 Linux Sistem Yöneticisi (SysAdmin Copilot)", "sysadmin")
        self.cb_persona.addItem("🤖 Genel Asistan", "general")
        self.cb_persona.addItem("💻 Kıdemli Yazılım Uzmanı", "coder")
        self.cb_persona.addItem("🧠 Derin Akıl Yürütme (Step-by-Step)", "reasoning")
        self.cb_persona.addItem("⚡ Kısa & Net (Özet)", "concise")
        self.cb_persona.currentIndexChanged.connect(self.on_persona_changed)
        persona_row.addWidget(lbl_p)
        persona_row.addWidget(self.cb_persona, 1)

        from PyQt6.QtWidgets import QCheckBox
        self.chk_autopilot = QCheckBox("⚡ Otonom Ajan (Zararsız komutları otomatik çalıştır)")
        self.chk_autopilot.setChecked(True)
        self.chk_autopilot.setStyleSheet("color: #9ece6a; font-weight: bold; font-size: 11px; margin-left: 10px;")
        self.chk_autopilot.setToolTip("Modelin önerdiği güvenli okuma komutlarını (uname, free, lspci vb.) onay beklemeden doğrudan çalıştırıp analiz eder.")
        persona_row.addWidget(self.chk_autopilot)
        layout.addLayout(persona_row)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { background: #16161e; border: 1px solid #292e42; border-radius: 8px; }")

        self.chat_container = QWidget()
        self.chat_container.setStyleSheet("background: transparent;")
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(12, 12, 12, 12)
        self.chat_layout.setSpacing(12)
        self.chat_layout.addStretch()

        self.scroll_area.setWidget(self.chat_container)
        layout.addWidget(self.scroll_area, 1)

        self.frame_img_preview = QFrame()
        self.frame_img_preview.setStyleSheet("background: #1f2335; border: 1px dashed #7aa2f7; border-radius: 6px; padding: 4px;")
        h_prev = QHBoxLayout(self.frame_img_preview)
        h_prev.setContentsMargins(6, 4, 6, 4)
        h_prev.setSpacing(8)

        self.lbl_img_thumb = QLabel()
        self.lbl_img_thumb.setFixedSize(40, 40)
        self.lbl_img_thumb.setStyleSheet("border-radius: 4px; background: #16161e;")
        h_prev.addWidget(self.lbl_img_thumb)

        self.lbl_img_info = QLabel()
        self.lbl_img_info.setStyleSheet("color: #7dcfff; font-size: 11px;")
        h_prev.addWidget(self.lbl_img_info, 1)

        self.btn_remove_img = QPushButton("✕")
        self.btn_remove_img.setAutoDefault(False)
        self.btn_remove_img.setDefault(False)
        self.btn_remove_img.setFixedSize(24, 24)
        self.btn_remove_img.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_remove_img.setStyleSheet("background: transparent; border: none; color: #f7768e; font-size: 13px; font-weight: bold;")
        self.btn_remove_img.clicked.connect(self.remove_attached_image)
        h_prev.addWidget(self.btn_remove_img)

        self.frame_img_preview.hide()
        layout.addWidget(self.frame_img_preview)

        # Alt Kontrol Çubuğu (Birleşik Buton Mimarisi)
        bot_box = QHBoxLayout()
        bot_box.setSpacing(6)

        self.btn_attach = QPushButton("🖼️")
        self.btn_attach.setAutoDefault(False)
        self.btn_attach.setDefault(False)
        self.btn_attach.setFixedSize(38, 38)
        self.btn_attach.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_attach.setToolTip("Görsel Ekle (PNG, JPG, WEBP) veya pencereye sürükleyin")
        self.btn_attach.setStyleSheet("background: #1f2335; border: 1px solid #3b4261; border-radius: 6px; font-size: 16px;")
        self.btn_attach.clicked.connect(self.pick_image_file)
        bot_box.addWidget(self.btn_attach)

        self.input_prompt = QLineEdit()
        self.input_prompt.setPlaceholderText("Mesaj yazın veya Linux sisteminizle ilgili bir soru sorun...")
        self.input_prompt.setFixedHeight(38)
        self.input_prompt.returnPressed.connect(self.on_action_triggered)
        bot_box.addWidget(self.input_prompt, 1)

        # BİRLEŞİK GÖNDER / DURDUR BUTONU
        self.btn_action = QPushButton("➤ Gönder")
        self.btn_action.setAutoDefault(False)
        self.btn_action.setDefault(False)
        self.btn_action.setFixedHeight(38)
        self.btn_action.setFixedWidth(95)
        self.btn_action.setStyleSheet("background: #7aa2f7; color: #15161e; font-weight: bold; font-size: 12px; border-radius: 6px;")
        self.btn_action.clicked.connect(self.on_action_triggered)
        bot_box.addWidget(self.btn_action)

        layout.addLayout(bot_box)
        self.init_system_persona()
        self.update_model_header()

    def set_generating_state(self, generating):
        self.is_generating = generating
        if generating:
            self.btn_action.setText("⏹ Durdur")
            self.btn_action.setStyleSheet("background: #f7768e; color: #15161e; font-weight: bold; font-size: 12px; border-radius: 6px;")
            self.btn_action.setToolTip("Yanıt üretimini durdur (Esc)")
            self.input_prompt.setEnabled(False)
            self.btn_attach.setEnabled(False)
        else:
            self.btn_action.setText("➤ Gönder")
            self.btn_action.setStyleSheet("background: #7aa2f7; color: #15161e; font-weight: bold; font-size: 12px; border-radius: 6px;")
            self.btn_action.setToolTip("Mesajı Gönder (Enter)")
            self.input_prompt.setEnabled(True)
            self.btn_attach.setEnabled(True)
            self.input_prompt.setFocus()

    def on_action_triggered(self):
        if self.is_generating:
            # Enter tuşunun aynı anda gönderip hemen iptal etmesini engelle (350ms koruma)
            if (time.time() - self._last_start_time) > 0.35:
                self.abort_generation()
        else:
            self.send_message()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.is_generating:
            self.abort_generation()
            event.accept()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.input_prompt.hasFocus() and not self.is_generating:
                self.send_message()
                event.accept()
            else:
                event.ignore()
        else:
            super().keyPressEvent(event)

    def copy_to_clip(self, text):
        QApplication.clipboard().setText(text)

    def init_system_persona(self):
        role_key = self.cb_persona.currentData()
        sys_prompt = PERSONAS.get(role_key, PERSONAS["sysadmin"])
        self.messages = [{"role": "system", "content": sys_prompt}]

    def on_persona_changed(self):
        role_key = self.cb_persona.currentData()
        sys_prompt = PERSONAS.get(role_key, PERSONAS["sysadmin"])
        if self.messages and self.messages[0]["role"] == "system":
            self.messages[0]["content"] = sys_prompt
        else:
            self.messages.insert(0, {"role": "system", "content": sys_prompt})

    def scroll_to_bottom(self):
        vs = self.scroll_area.verticalScrollBar()
        vs.setValue(vs.maximum())

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                fpath = url.toLocalFile().lower()
                if fpath.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
                    event.acceptProposedAction()
                    return
        super().dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                fpath = url.toLocalFile()
                if fpath.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")):
                    self.attach_image(fpath)
                    event.acceptProposedAction()
                    return
        super().dropEvent(event)

    def pick_image_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Görsel Seç", os.path.expanduser("~"), "Görsel Dosyaları (*.png *.jpg *.jpeg *.webp *.bmp)")
        if f:
            self.attach_image(f)

    def attach_image(self, file_path):
        if not os.path.exists(file_path):
            return
        ext = os.path.splitext(file_path)[1].lower().replace(".", "")
        if ext == "jpg": ext = "jpeg"
        mime = f"image/{ext}" if ext in ["jpeg", "png", "webp", "bmp"] else "image/jpeg"

        try:
            with open(file_path, "rb") as img_f:
                b64_data = base64.b64encode(img_f.read()).decode("utf-8")

            self.current_attached_image = {
                "path": file_path,
                "mime": mime,
                "b64": b64_data,
                "filename": os.path.basename(file_path)
            }
            pix = QPixmap(file_path)
            self.lbl_img_thumb.setPixmap(pix.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            size_kb = round(os.path.getsize(file_path) / 1024, 1)
            self.lbl_img_info.setText(f"🖼️ <b>{os.path.basename(file_path)}</b> ({size_kb} KB)")
            self.frame_img_preview.show()
            self.input_prompt.setFocus()
        except Exception as e:
            QMessageBox.warning(self, "Görsel Hatası", f"Görsel okunamadı: {e}")

    def remove_attached_image(self):
        self.current_attached_image = None
        self.frame_img_preview.hide()

    def update_model_header(self):
        m_id = self.active_model_func()
        if m_id:
            self.lbl_model_badge.setText(f"🤖 <b>Aktif Model:</b> {m_id}")
            self.input_prompt.setEnabled(True)
            self.btn_action.setEnabled(True)
            self.btn_attach.setEnabled(True)
        else:
            self.lbl_model_badge.setText("⚠️ <b>Bellekte Model Yok</b> — Lütfen önce Modeller sekmesinden bir model yükleyin.")
            self.input_prompt.setEnabled(False)
            self.btn_action.setEnabled(False)
            self.btn_attach.setEnabled(False)

    def clear_chat(self):
        if self.is_generating:
            self.abort_generation()
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()
        self.remove_attached_image()
        self.init_system_persona()
        self.update_model_header()

    def export_chat_markdown(self):
        if len(self.messages) <= 1:
            QMessageBox.information(self, "Bilgi", "Kaydedilecek sohbet geçmişi bulunmuyor.")
            return

        fpath, _ = QFileDialog.getSaveFileName(self, "Sohbeti Kaydet", os.path.expanduser("~/sohbet.md"), "Markdown (*.md)")
        if not fpath:
            return

        try:
            m_id = self.active_model_func() or "Model"
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(f"# Tray-AI Sohbet Günlüğü\n- **Model:** {m_id}\n- **Tarih:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n")
                for m in self.messages:
                    role = m.get("role", "")
                    content = m.get("content", "")
                    if role == "system":
                        f.write(f"> **Sistem Rolü:** {content}\n\n")
                    elif role == "user":
                        c_text = content
                        if isinstance(content, list):
                            for sub in content:
                                if sub.get("type") == "text":
                                    c_text = sub.get("text", "")
                        f.write(f"### 👤 Kullanıcı\n{c_text}\n\n")
                    elif role == "assistant":
                        f.write(f"### 🤖 Asistan ({m_id})\n{content}\n\n")
            QMessageBox.information(self, "Başarılı", f"Sohbet başarıyla kaydedildi:\n{fpath}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Dosya kaydedilemedi:\n{e}")

    def send_automated_prompt(self, prompt_text, visible_title=None):
        if self.is_generating:
            return
        display_text = visible_title or prompt_text
        self.messages.append({"role": "user", "content": prompt_text})

        user_row = QHBoxLayout()
        user_row.addStretch(1)
        user_b = UserBubble(display_text, None)
        user_row.addWidget(user_b)
        self.chat_layout.insertLayout(self.chat_layout.count() - 1, user_row)

        m_id = self.active_model_func() or "Model"
        ai_row = QHBoxLayout()
        ai_b = AssistantBubble(m_id, self)
        ai_row.addWidget(ai_b)
        ai_row.addStretch(1)
        self.chat_layout.insertLayout(self.chat_layout.count() - 1, ai_row)
        self.current_active_bubble = ai_b

        QTimer.singleShot(15, self.scroll_to_bottom)
        self._last_start_time = time.time()
        self.set_generating_state(True)

        self.worker = ChatStreamWorker(self.engine_port, m_id, self.messages)
        self.worker.chunk_received.connect(self.on_chunk)
        self.worker.stats_ready.connect(self.on_stats)
        self.worker.finished_ok.connect(self.on_finish)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()

    def send_message(self):
        if self.is_generating:
            return

        raw_text = self.input_prompt.text().strip()
        has_img = self.current_attached_image is not None

        if not raw_text and not has_img:
            return

        m_id = self.active_model_func()
        if not m_id:
            QMessageBox.warning(self, "Model Yok", "Lütfen önce bir model yükleyin.")
            return

        text = raw_text if raw_text else ("Bu görseli detaylı açıkla ve analiz et." if has_img else "")
        self.input_prompt.clear()

        img_p = None
        if has_img:
            img_p = self.current_attached_image["path"]
            img_b64 = self.current_attached_image["b64"]
            img_mime = self.current_attached_image["mime"]
            content_payload = [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": f"data:{img_mime};base64,{img_b64}"}}
            ]
            self.messages.append({"role": "user", "content": content_payload})
            self.remove_attached_image()
        else:
            self.messages.append({"role": "user", "content": text})

        user_row = QHBoxLayout()
        user_row.addStretch(1)
        user_b = UserBubble(text, img_p)
        user_row.addWidget(user_b)
        self.chat_layout.insertLayout(self.chat_layout.count() - 1, user_row)

        ai_row = QHBoxLayout()
        ai_b = AssistantBubble(m_id, self)
        ai_row.addWidget(ai_b)
        ai_row.addStretch(1)
        self.chat_layout.insertLayout(self.chat_layout.count() - 1, ai_row)
        self.current_active_bubble = ai_b

        QTimer.singleShot(15, self.scroll_to_bottom)
        self._last_start_time = time.time()
        self.set_generating_state(True)

        self.worker = ChatStreamWorker(self.engine_port, m_id, self.messages)
        self.worker.chunk_received.connect(self.on_chunk)
        self.worker.stats_ready.connect(self.on_stats)
        self.worker.finished_ok.connect(self.on_finish)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()

    def on_chunk(self, chunk, is_thinking):
        if not self.current_active_bubble or not self.is_generating:
            return
        if is_thinking:
            self.current_active_bubble.append_thinking(chunk)
        else:
            self.current_active_bubble.append_response(chunk)
        self.scroll_to_bottom()

    def on_stats(self, ttft, speed, tokens):
        if self.current_active_bubble and self.is_generating:
            self.current_active_bubble.set_stats(ttft, speed, tokens)
            self.scroll_to_bottom()

    def on_finish(self):
        if not self.is_generating:
            return
        self.is_generating = False
        self._last_start_time = 0.0
        if self.current_active_bubble:
            self.current_active_bubble.finalize_markdown()
            full_ans = self.current_active_bubble.response_buffer
            if full_ans:
                self.messages.append({"role": "assistant", "content": full_ans})
        self.set_generating_state(False)
        self.scroll_to_bottom()

    def on_error(self, err):
        if not self.is_generating:
            return
        if self.current_active_bubble:
            self.current_active_bubble.set_error(err)
        self.on_finish()

    def abort_generation(self):
        if not self.is_generating:
            return
        self.is_generating = False
        self._last_start_time = 0.0

        if self.worker:
            try:
                self.worker.chunk_received.disconnect()
            except Exception:
                pass
            try:
                self.worker.stats_ready.disconnect()
            except Exception:
                pass
            try:
                self.worker.finished_ok.disconnect()
            except Exception:
                pass
            try:
                self.worker.error_occurred.disconnect()
            except Exception:
                pass
            self.worker.abort()
            self.worker.wait(300)
            self.worker = None

        if self.current_active_bubble:
            self.current_active_bubble.append_response("\n\n🛑 *[Yanıt kullanıcı tarafından durduruldu]*")
            self.current_active_bubble.finalize_markdown(suppress_auto_run=True)
            full_ans = self.current_active_bubble.response_buffer
            if full_ans:
                self.messages.append({"role": "assistant", "content": full_ans})

        self.set_generating_state(False)
        self.scroll_to_bottom()
