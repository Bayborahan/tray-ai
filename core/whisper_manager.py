import os
import signal
import subprocess
import requests
import shutil
from PyQt6.QtCore import QThread, pyqtSignal

WHISPER_MODELS_DIR = os.path.expanduser("~/.local/share/tray-ai/whisper_models")
os.makedirs(WHISPER_MODELS_DIR, exist_ok=True)

DEFAULT_MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
AUDIO_TMP_PATH = "/tmp/tray_ai_speech.wav"

class WhisperDownloadWorker(QThread):
    progress = pyqtSignal(int, str)
    finished_ok = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, target_path=None, model_url=DEFAULT_MODEL_URL):
        super().__init__()
        self.model_url = model_url
        self.target_path = target_path or os.path.join(WHISPER_MODELS_DIR, "ggml-base.bin")

    def run(self):
        try:
            self.progress.emit(5, "Whisper modeli indiriliyor (~140 MB)...")
            r = requests.get(self.model_url, stream=True, timeout=30)
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            part_path = self.target_path + ".part"

            with open(part_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = int((downloaded / total) * 90)
                            self.progress.emit(5 + pct, f"İndiriliyor: {downloaded // (1024*1024)} / {total // (1024*1024)} MB")

            os.replace(part_path, self.target_path)
            self.progress.emit(100, "Model hazır!")
            self.finished_ok.emit(self.target_path)
        except Exception as e:
            self.error.emit(str(e))


class AudioRecorder:
    def __init__(self):
        self.process = None

    def start_recording(self, output_path=AUDIO_TMP_PATH):
        if not shutil.which("arecord"):
            raise RuntimeError("Sistemde 'arecord' bulunamadı! 'sudo apt install alsa-utils' çalıştırın.")

        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception:
                pass

        # 16kHz, 16-bit, Mono WAV kaydı
        cmd = [
            "arecord",
            "-q",
            "-t", "wav",
            "-f", "S16_LE",
            "-r", "16000",
            "-c", "1",
            output_path
        ]
        self.process = subprocess.Popen(cmd, preexec_fn=os.setsid)

    def stop_recording(self):
        if self.process and self.process.poll() is None:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=2)
            except Exception:
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except Exception:
                    pass
        self.process = None


class TranscribeWorker(QThread):
    finished_text = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, engines_dir, model_path, audio_path=AUDIO_TMP_PATH, lang="tr"):
        super().__init__()
        self.engines_dir = engines_dir
        self.model_path = model_path
        self.audio_path = audio_path
        self.lang = lang

    def run(self):
        bin_path = os.path.join(self.engines_dir, "whisper-cli")
        if not os.path.exists(bin_path):
            self.error.emit(f"whisper-cli bulunamadı: {bin_path}")
            return

        if not os.path.exists(self.model_path):
            self.error.emit(f"Whisper modeli bulunamadı: {self.model_path}")
            return

        if not os.path.exists(self.audio_path) or os.path.getsize(self.audio_path) < 1000:
            self.error.emit("Ses kaydı algılanamadı veya çok kısa.")
            return

        try:
            env = os.environ.copy()
            env["LD_LIBRARY_PATH"] = f"{self.engines_dir}:{env.get('LD_LIBRARY_PATH', '')}"

            cmd = [
                bin_path,
                "-m", self.model_path,
                "-f", self.audio_path,
                "-l", self.lang,
                "-nt"  # Zaman damgalarını gizle, sadece metin ver
            ]

            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True, env=env, timeout=60)
            cleaned = out.strip()
            self.finished_text.emit(cleaned)
        except Exception as e:
            self.error.emit(f"Deşifre hatası: {str(e)}")
