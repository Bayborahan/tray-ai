import json
import time
import base64
import os
import requests
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextBrowser, QMessageBox,
    QFileDialog, QFrame
)
from PyQt6.QtGui import QTextCursor, QPixmap
from ui.styles import DARK_STYLE

class ChatStreamWorker(QThread):
    chunk_received = pyqtSignal(str, bool)
    stats_ready = pyqtSignal(float, float, int)
    finished_ok = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, port, model_id, messages):
        super().__init__()
        self.port = port
        self.model_id = model_id
        self.messages = messages
        self._is_aborted = False

    def abort(self):
        self._is_aborted = True

    def run(self):
        url = f"http://127.0.0.1:{self.port}/v1/chat/completions"
        payload = {
            "model": self.model_id,
            "messages": self.messages,
            "stream": True,
            "temperature": 0.7
        }

        start_time = time.time()
        first_token_time = None
        token_count = 0
        in_thinking_tag = False

        try:
            resp = requests.post(url, json=payload, stream=True, timeout=180)
            if resp.status_code != 200:
                self.error_occurred.emit(f"HTTP {resp.status_code}: {resp.text[:200]}")
                return

            for line in resp.iter_lines():
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
                                if parts[0]:
                                    self.chunk_received.emit(parts[0], True)
                                if len(parts) > 1 and parts[1]:
                                    self.chunk_received.emit(parts[1], False)
                                continue

                            if content_part:
                                self.chunk_received.emit(content_part, in_thinking_tag)

                    except Exception:
                        pass

            end_time = time.time()
            ttft = (first_token_time - start_time) if first_token_time else 0.0
            gen_duration = max(0.01, end_time - (first_token_time or start_time))
            speed = (token_count / gen_duration) if token_count > 0 else 0.0

            self.stats_ready.emit(ttft, speed, token_count)
            self.finished_ok.emit()

        except Exception as e:
            if not self._is_aborted:
                self.error_occurred.emit(str(e))


class ChatTesterDialog(QDialog):
    def __init__(self, parent, gateway_port, active_model_func):
        super().__init__(parent)
        self.gateway_port = gateway_port
        self.active_model_func = active_model_func
        self.setWindowTitle("💬 Model Test Sohbeti (Playground & Vision)")
        self.resize(640, 750)
        self.setStyleSheet(DARK_STYLE)
        self.setAcceptDrops(True)

        self.messages = []
        self.worker = None
        self._current_assistant_buffer = ""
        self._is_in_thinking_mode = False
        self.current_attached_image = None

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # Üst Bilgi Barı
        top_box = QHBoxLayout()
        self.lbl_model_badge = QLabel()
        self.lbl_model_badge.setStyleSheet(
            "background: #1f2335; border: 1px solid #3b4261; border-left: 3px solid #7aa2f7; "
            "padding: 6px 10px; border-radius: 6px; font-size: 12px; color: #7dcfff;"
        )
        top_box.addWidget(self.lbl_model_badge, 1)

        btn_clear = QPushButton("🧹 Temizle")
        btn_clear.setFixedHeight(28)
        btn_clear.setStyleSheet("background: #24283b; border: 1px solid #414868; font-size: 11px;")
        btn_clear.clicked.connect(self.clear_chat)
        top_box.addWidget(btn_clear)
        layout.addLayout(top_box)

        # Sohbet Ekranı
        self.chat_display = QTextBrowser()
        self.chat_display.setStyleSheet(
            "QTextBrowser { background: #16161e; border: 1px solid #292e42; border-radius: 8px; "
            "padding: 10px; font-family: Ubuntu, Segoe UI, sans-serif; font-size: 13px; color: #c0caf5; }"
        )
        layout.addWidget(self.chat_display, 1)

        # Görsel Yükleme Önizleme Barı (Başlangıçta gizli)
        self.frame_img_preview = QFrame()
        self.frame_img_preview.setStyleSheet("""
            QFrame {
                background: #1f2335;
                border: 1px dashed #7aa2f7;
                border-radius: 6px;
                padding: 4px;
            }
        """)
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
        self.btn_remove_img.setFixedSize(24, 24)
        self.btn_remove_img.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_remove_img.setStyleSheet("""
            QPushButton { background: transparent; border: none; color: #f7768e; font-size: 13px; font-weight: bold; }
            QPushButton:hover { background: rgba(247, 118, 142, 0.2); border-radius: 12px; }
        """)
        self.btn_remove_img.clicked.connect(self.remove_attached_image)
        h_prev.addWidget(self.btn_remove_img)

        self.frame_img_preview.hide()
        layout.addWidget(self.frame_img_preview)

        # Alt Girdi Çubuğu
        bot_box = QHBoxLayout()
        bot_box.setSpacing(6)

        # Görsel Seçici Butonu
        self.btn_attach = QPushButton("🖼️")
        self.btn_attach.setFixedSize(38, 38)
        self.btn_attach.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_attach.setToolTip("Görsel Ekle (PNG, JPG, WEBP) veya pencereye sürükleyip bırakın")
        self.btn_attach.setStyleSheet("""
            QPushButton {
                background: #1f2335;
                border: 1px solid #3b4261;
                border-radius: 6px;
                font-size: 16px;
            }
            QPushButton:hover {
                background: #24283b;
                border-color: #7aa2f7;
            }
        """)
        self.btn_attach.clicked.connect(self.pick_image_file)
        bot_box.addWidget(self.btn_attach)

        self.input_prompt = QLineEdit()
        self.input_prompt.setPlaceholderText("Mesaj yazın veya görsel sürükleyip bırakın...")
        self.input_prompt.setFixedHeight(38)
        self.input_prompt.returnPressed.connect(self.send_message)
        bot_box.addWidget(self.input_prompt, 1)

        self.btn_send = QPushButton("➤ Gönder")
        self.btn_send.setFixedHeight(38)
        self.btn_send.setFixedWidth(85)
        self.btn_send.setStyleSheet("background: #7aa2f7; color: #15161e; font-weight: bold; font-size: 12px; border-radius: 6px;")
        self.btn_send.clicked.connect(self.send_message)
        bot_box.addWidget(self.btn_send)

        self.btn_stop = QPushButton("🛑")
        self.btn_stop.setFixedHeight(38)
        self.btn_stop.setFixedWidth(38)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("background: #f7768e; color: #15161e; font-weight: bold; border-radius: 6px;")
        self.btn_stop.clicked.connect(self.abort_generation)
        bot_box.addWidget(self.btn_stop)

        layout.addLayout(bot_box)
        self.update_model_header()

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
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Görsel Seç",
            os.path.expanduser("~"),
            "Görsel Dosyaları (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if f:
            self.attach_image(f)

    def attach_image(self, file_path):
        if not os.path.exists(file_path):
            return
        ext = os.path.splitext(file_path)[1].lower().replace(".", "")
        if ext == "jpg":
            ext = "jpeg"
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
            self.lbl_img_thumb.setPixmap(
                pix.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
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
            self.btn_send.setEnabled(True)
            self.btn_attach.setEnabled(True)
        else:
            self.lbl_model_badge.setText("⚠️ <b>Bellekte Model Yok</b> — Lütfen önce Modeller sekmesinden bir model yükleyin.")
            self.input_prompt.setEnabled(False)
            self.btn_send.setEnabled(False)
            self.btn_attach.setEnabled(False)

    def clear_chat(self):
        self.messages.clear()
        self.chat_display.clear()
        self.remove_attached_image()
        self.update_model_header()

    def send_message(self):
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

        # Mesaj içeriğini oluştur
        escaped_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")

        img_html = ""
        if has_img:
            img_path = self.current_attached_image["path"]
            img_b64 = self.current_attached_image["b64"]
            img_mime = self.current_attached_image["mime"]

            content_payload = [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": f"data:{img_mime};base64,{img_b64}"}}
            ]
            self.messages.append({"role": "user", "content": content_payload})

            img_html = f"<img src='{img_path}' width='200' style='border-radius: 6px; margin: 4px 0;'><br>"
            self.remove_attached_image()
        else:
            self.messages.append({"role": "user", "content": text})

        user_card = (
            "<div style='margin: 8px 0; text-align: right;'>"
            "<div style='display: inline-block; background: #24283b; border: 1px solid #3b4261; border-radius: 8px; padding: 8px 12px; text-align: left; max-width: 85%;'>"
            "<span style='color: #7dcfff; font-weight: bold; font-size: 11px;'>👤 Sen</span><br>"
            + img_html +
            f"<span style='color: #c0caf5;'>{escaped_text}</span>"
            "</div></div>"
        )
        self.chat_display.append(user_card)

        ai_head = f"<div style='margin-top: 10px;'><span style='color: #bb9af7; font-weight: bold; font-size: 11px;'>🤖 {m_id}</span></div>"
        self.chat_display.append(ai_head)

        self._current_assistant_buffer = ""
        self._is_in_thinking_mode = False

        self.btn_send.setEnabled(False)
        self.input_prompt.setEnabled(False)
        self.btn_attach.setEnabled(False)
        self.btn_stop.setEnabled(True)

        self.worker = ChatStreamWorker(self.gateway_port, m_id, self.messages)
        self.worker.chunk_received.connect(self.on_chunk)
        self.worker.stats_ready.connect(self.on_stats)
        self.worker.finished_ok.connect(self.on_finish)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()

    def on_chunk(self, chunk, is_thinking):
        self._current_assistant_buffer += chunk

        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        if is_thinking:
            if not self._is_in_thinking_mode:
                self._is_in_thinking_mode = True
                cursor.insertHtml("<br><span style='color: #7a829e; font-style: italic; font-size: 12px;'>💭 <b>Düşünce Zinciri:</b><br>")
            cursor.insertText(chunk)
        else:
            if self._is_in_thinking_mode:
                self._is_in_thinking_mode = False
                cursor.insertHtml("</span><br><br>")
            cursor.insertText(chunk)

        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

    def on_stats(self, ttft, speed, tokens):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        stat_html = f"<br><span style='font-size: 11px; color: #73daca; font-weight: bold;'>⚡ TTFT: {ttft*1000:.0f} ms • Hız: {speed:.1f} t/s • Toplam: {tokens} token</span><br>"
        cursor.insertHtml(stat_html)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.ensureCursorVisible()

    def on_finish(self):
        if self._current_assistant_buffer:
            self.messages.append({"role": "assistant", "content": self._current_assistant_buffer})
        self.btn_send.setEnabled(True)
        self.input_prompt.setEnabled(True)
        self.btn_attach.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.input_prompt.setFocus()

    def on_error(self, err):
        self.chat_display.append(f"<span style='color:#f7768e;'>❌ Hata: {err}</span>")
        self.on_finish()

    def abort_generation(self):
        if self.worker:
            self.worker.abort()
        self.btn_stop.setEnabled(False)
        self.chat_display.append("<span style='color:#e0af68; font-size:11px;'>🛑 <i>[Üretim kesildi]</i></span>")
        self.on_finish()
