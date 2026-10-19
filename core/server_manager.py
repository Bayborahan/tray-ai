import subprocess
import os
import signal
import time
import requests
from PyQt6.QtCore import QThread, pyqtSignal

class ServerLogReader(QThread):
    log_line = pyqtSignal(str)
    load_progress = pyqtSignal(int, str)
    server_ready = pyqtSignal()
    server_stopped = pyqtSignal(int)
    tool_call_detected = pyqtSignal(str)

    def __init__(self, process, port=8080, total_layers=32):
        super().__init__()
        self.process = process
        self.port = port
        self.total_layers = max(1, total_layers)
        self._running = True
        self._is_ready = False

    def run(self):
        pct = 5
        self.load_progress.emit(pct, "Motor başlatılıyor...")
        try:
            for line in iter(self.process.stdout.readline, ''):
                if not self._running:
                    break
                clean = line.strip()
                if not clean:
                    continue
                self.log_line.emit(clean)
                low = clean.lower()

                if not self._is_ready:
                    if "llama_model_loader" in low or "kv" in low or "meta" in low:
                        pct = min(35, pct + 2)
                        self.load_progress.emit(pct, "Model yapısı ve metadata okunuyor...")
                    elif "load_tensors" in low or "offloaded" in low or "buffer size" in low or "vulkan" in low:
                        pct = min(85, pct + 8)
                        self.load_progress.emit(pct, "Tensorlar RAM / VRAM'e aktarılıyor...")
                    elif "llama_context" in low or "kv_cache" in low or "flash_attn" in low:
                        pct = 92
                        self.load_progress.emit(pct, "Context ve K/V Cache ayrılıyor...")
                    elif any(k in low for k in ["server is listening", "http server", "main: model loaded", "starting the main loop", "listening on"]):
                        self._is_ready = True
                        self.load_progress.emit(100, "Model yüklendi ve kullanıma hazır!")
                        self.server_ready.emit()

                if any(t in low for t in ["tool_calls", "<tool_call>", "\"tools\":", "function_call"]):
                    self.tool_call_detected.emit("🔧 Uzak İstemci Araç / Ajan (Tool) Çağrısı Aktif")

            ret = self.process.wait()
            self.server_stopped.emit(ret)
        except Exception as e:
            self.log_line.emit(f"[Log Uyarı]: {e}")

    def mark_ready_external(self):
        if not self._is_ready:
            self._is_ready = True
            self.load_progress.emit(100, "Model yüklendi ve kullanıma hazır!")
            self.server_ready.emit()

    def stop_reading(self):
        self._running = False


class TelemetryPoller(QThread):
    health_ready = pyqtSignal()
    loading_tick = pyqtSignal()
    telemetry_update = pyqtSignal(dict)

    def __init__(self, port=8080):
        super().__init__()
        self.port = port
        self._running = True
        self._model_ready = False
        self._gen_start_time = 0
        self._was_generating = False

    def set_port(self, port):
        self.port = port

    def reset_ready(self):
        self._model_ready = False

    def stop(self):
        self._running = False

    def run(self):
        session = requests.Session()
        while self._running:
            base_url = f"http://127.0.0.1:{self.port}"
            try:
                if not self._model_ready:
                    r = session.get(f"{base_url}/health", timeout=0.4)
                    if r.status_code == 200:
                        data = r.json()
                        if data.get("status") == "ok":
                            self._model_ready = True
                            self.health_ready.emit()
                    elif r.status_code == 503:
                        self.loading_tick.emit()
                else:
                    r = session.get(f"{base_url}/slots", timeout=0.4)
                    if r.status_code == 200:
                        slots = r.json()
                        if isinstance(slots, list) and len(slots) > 0:
                            active_slot = slots[0]
                            for s in slots:
                                if s.get("is_processing") or s.get("state", 0) != 0:
                                    active_slot = s
                                    break
                            self._parse_and_emit_slot(active_slot)
            except Exception:
                pass

            self.msleep(250)

    def _parse_and_emit_slot(self, s):
        state = s.get("state", 0)
        is_proc = s.get("is_processing", state != 0)
        n_ctx = s.get("n_ctx", 4096)

        nt = s.get("next_token", {})
        if isinstance(nt, list) and len(nt) > 0:
            nt = nt[0]
        elif not isinstance(nt, dict):
            nt = {}

        n_decoded = nt.get("n_decoded", s.get("n_decoded", 0))
        n_past = s.get("n_past", 0)
        n_prompt = s.get("n_prompt_tokens", s.get("n_prompt_tokens_processed", 0))

        timings = s.get("timings", {})
        pp_speed = timings.get("prompt_per_second", 0.0)
        tg_speed = timings.get("predicted_per_second", 0.0)

        grammar = str(s.get("grammar", "")) + str(s.get("params", {}).get("grammar", ""))
        has_tool_grammar = len(grammar.strip()) > 0 or "tool" in str(s).lower()

        info = {
            "is_processing": is_proc,
            "state": state,
            "n_ctx": n_ctx,
            "n_past": n_past,
            "n_decoded": n_decoded,
            "n_prompt": n_prompt,
            "prompt_pct": 100,
            "pp_speed": pp_speed,
            "tg_speed": tg_speed,
            "is_tool_call": has_tool_grammar
        }

        if is_proc:
            if not self._was_generating:
                self._was_generating = True
                self._gen_start_time = time.time()

            elapsed = max(0.1, time.time() - self._gen_start_time)

            if state == 1 or (n_decoded == 0 and n_past == 0):
                info["phase"] = "prompt"
                if n_prompt > 0 and n_past > 0:
                    info["prompt_pct"] = min(99, int((n_past / n_prompt) * 100))
                else:
                    info["prompt_pct"] = min(95, int((elapsed * 35) % 100))
            else:
                info["phase"] = "eval"
                if n_decoded > 0:
                    info["tokens_generated"] = n_decoded
                    if tg_speed <= 0:
                        info["tg_speed"] = round(n_decoded / elapsed, 1)
                else:
                    info["tokens_generated"] = n_past
        else:
            self._was_generating = False
            info["phase"] = "idle"
            info["tokens_generated"] = n_decoded if n_decoded > 0 else n_past

        self.telemetry_update.emit(info)


class ServerManager:
    def __init__(self, engines_dir="engines"):
        self.engines_dir = os.path.abspath(engines_dir)
        self.process = None
        self.reader_thread = None

    def get_library_env(self, extra_env=None):
        run_env = os.environ.copy()
        lib_paths = [self.engines_dir]
        for root, dirs, _ in os.walk(self.engines_dir):
            for d in dirs:
                lib_paths.append(os.path.join(root, d))
        existing_ld = run_env.get("LD_LIBRARY_PATH", "")
        if existing_ld:
            lib_paths.append(existing_ld)
        run_env["LD_LIBRARY_PATH"] = ":".join(lib_paths)
        if extra_env:
            run_env.update(extra_env)
        return run_env

    def start_model(self, engine_name, model_path, host="127.0.0.1", port=8080, 
                    ngl=99, ctx=4096, extra_flags=None, env_vars=None, total_layers=32):
        if self.is_running():
            self.stop_model()

        engine_path = os.path.join(self.engines_dir, engine_name)
        if not os.path.exists(engine_path):
            # Fallback kontrolü: Proje dizininde veya /opt/tray-ai/engines altında var mı?
            fallback_paths = [
                os.path.join(BASE_DIR, "engines", engine_name),
                os.path.join("/opt/tray-ai/engines", engine_name)
            ]
            found = False
            for fb in fallback_paths:
                if os.path.exists(fb):
                    import shutil
                    os.makedirs(self.engines_dir, exist_ok=True)
                    shutil.copy2(fb, engine_path)
                    os.chmod(engine_path, 0o755)
                    found = True
                    break
            if not found:
                raise FileNotFoundError(f"Motor bulunamadı: {engine_path}\nLütfen Ayarlar (⚙️) -> Runtime & Engines bölümünden motoru indirin veya güncelleyin.")

        os.chmod(engine_path, 0o755)

        cmd = [
            engine_path,
            "-m", model_path,
            "--host", host,
            "--port", str(port),
            "-ngl", str(ngl),
            "-c", str(ctx),
            "--slots",
            "--metrics"
        ]

        if extra_flags:
            cmd.extend(extra_flags)

        run_env = self.get_library_env(env_vars)

        # start_new_session=True sayesinde alt süreç grubu oluşturulur, kapatılırken RAM anında boşaltılır
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=self.engines_dir,
            env=run_env,
            start_new_session=True
        )

        self.reader_thread = ServerLogReader(self.process, port=port, total_layers=total_layers)
        self.reader_thread.start()
        return self.reader_thread

    def stop_model(self):
        if self.reader_thread:
            self.reader_thread.stop_reading()
        if self.process and self.process.poll() is None:
            try:
                pgid = os.getpgid(self.process.pid)
                os.killpg(pgid, signal.SIGTERM)
            except Exception:
                self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    pgid = os.getpgid(self.process.pid)
                    os.killpg(pgid, signal.SIGKILL)
                except Exception:
                    self.process.kill()
                self.process.wait(timeout=1)
        self.process = None

    def is_running(self):
        return self.process is not None and self.process.poll() is None
