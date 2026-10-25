# TRAY-AI PROJE HAFIZA VE KAYNAK KOD DÖKÜMANI
- **Son Güncelleme:** 2026-10-25 20:17
- **Git Commit:** 42f85b2 (2026-10-23 00:16:45 +0300)

## 1. Geliştirici ve Donanım Profili
- **Geliştirici:** Baybora (Elektronik ve yazılım uzmanı).
- **İşletim Sistemi:** Linux Mint (Sadece saf Linux mimarisi).
- **Ana Donanım:** AMD Ryzen 7 8700G (Radeon 780M iGPU), 96GB DDR5 RAM, AMD Radeon RX 6600 dGPU.
- **İkinci Sistem:** AMD Ryzen 7 5700G, 64GB DDR4 RAM.
- **Odak / Hedef:** Yerel LLM'leri düşük maliyetle, yüksek verimle ve saf Linux üzerinde Vulkan hızlandırmasıyla çalıştırmak.

## 2. Proje Mimarisi ve Temel Kurallar
- **Adı:** Tray-AI
- **Arayüz:** PyQt6 (Sistem tepsisi odaklı, modern kart tasarımlı arayüz).
- **Çalışma Prensibi:** GGUF modellerini yönetir, bağımsız Vulkan/AVX2 destekli `llama-server` sürecini (PID) kontrol eder.
- **Dağıtım Biçimi:** All-in-one bağımsız paket (.deb ve .rpm). `engines/llama-server` ikilisini içine gömer, harici kütüphane bağımlılığı istemez.

---

## 3. PROJE DİZİN AĞACI
```text
.
./assets
./assets/tray-ai.svg
./CONTEXT.md
./core
./core/api_gateway.py
./core/cache_manager.py
./core/engine_updater.py
./core/gguf_parser.py
./core/hardware.py
./core/hf_downloader.py
./core/__init__.py
./core/server_manager.py
./core/whisper_manager.py
./engines
./engines/.gitkeep
./engines/libggml-base.so
./engines/libggml-base.so.0
./engines/libggml-base.so.0.26.0
./engines/libggml-base.so.0.27.0
./engines/libggml-cpu-alderlake.so
./engines/libggml-cpu-cannonlake.so
./engines/libggml-cpu-cascadelake.so
./engines/libggml-cpu-cooperlake.so
./engines/libggml-cpu-haswell.so
./engines/libggml-cpu-icelake.so
./engines/libggml-cpu-ivybridge.so
./engines/libggml-cpu-piledriver.so
./engines/libggml-cpu-sandybridge.so
./engines/libggml-cpu-sapphirerapids.so
./engines/libggml-cpu-skylakex.so
./engines/libggml-cpu.so
./engines/libggml-cpu.so.0
./engines/libggml-cpu.so.0.27.0
./engines/libggml-cpu-sse42.so
./engines/libggml-cpu-x64.so
./engines/libggml-cpu-zen4.so
./engines/libggml-rpc.so
./engines/libggml.so
./engines/libggml.so.0
./engines/libggml.so.0.26.0
./engines/libggml.so.0.27.0
./engines/libggml-vulkan.so
./engines/libggml-vulkan.so.0
./engines/libggml-vulkan.so.0.27.0
./engines/libllama-batched-bench-impl.so
./engines/libllama-bench-impl.so
./engines/libllama-cli-impl.so
./engines/libllama-common.so
./engines/libllama-common.so.0
./engines/libllama-common.so.0.6.0
./engines/libllama-common.so.0.7.0
./engines/libllama-completion-impl.so
./engines/libllama-fit-params-impl.so
./engines/libllama-perplexity-impl.so
./engines/libllama-quantize-impl.so
./engines/libllama-server-impl.so
./engines/libllama.so
./engines/libllama.so.0
./engines/libllama.so.0.6.0
./engines/libllama.so.0.7.0
./engines/libmtmd.so
./engines/libmtmd.so.0
./engines/libmtmd.so.0.6.0
./engines/libmtmd.so.0.7.0
./engines/llama-server
./engines/whisper-cli
./generate_full_context.sh
./.gitattributes
./.github
./.github/workflows
./.github/workflows/package.yml
./.gitignore
./lang
./lang/en.json
./lang/tr.json
./LICENSE
./main.py
./models
./README.md
./requirements.txt
./run.sh
./run_step3_git_and_context.sh
./ui
./ui/chat_dialog.py
./ui/__init__.py
./ui/styles.py
./ui/tabs
./ui/tabs/__init__.py
./update_context.sh
```

# 4. PROJE DOSYALARI VE KAYNAK KODLAR

## Dosya: core/api_gateway.py
```python
import json
import time
import os
import requests
from datetime import datetime, timezone
from urllib.parse import urlparse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from PyQt6.QtCore import QThread, pyqtSignal

class GatewayRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Max-Age", "86400")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        clean_path = parsed.path.rstrip("/").lower()

        # 1. Ollama /api/version
        if clean_path in ("/api/version", "/version"):
            resp = json.dumps({"version": "0.5.4"}).encode("utf-8")
            self._send_json_response(200, resp)
            return

        # 2. OpenAI /v1/models ve /models
        if clean_path in ("/v1/models", "/models"):
            models_list = self.server.gateway_ref.get_all_models_callback()
            active_id = self.server.gateway_ref.get_active_model_id_callback()

            data = []
            for m in models_list:
                clean_id = os.path.splitext(m.get("filename", "model.gguf"))[0]
                data.append({
                    "id": clean_id,
                    "object": "model",
                    "created": int(m.get("mtime", time.time())),
                    "owned_by": m.get("publisher", "local"),
                    "permission": [],
                    "root": clean_id,
                    "parent": None,
                    "active": (clean_id == active_id)
                })

            resp = json.dumps({"object": "list", "data": data}, ensure_ascii=False).encode("utf-8")
            self._send_json_response(200, resp)
            return

        # 3. Ollama /api/tags
        if clean_path in ("/api/tags", "/tags"):
            models_list = self.server.gateway_ref.get_all_models_callback()
            ollama_models = []
            for m in models_list:
                clean_id = os.path.splitext(m.get("filename", "model.gguf"))[0]
                m_time = m.get("mtime", time.time())
                iso_time = datetime.fromtimestamp(m_time, tz=timezone.utc).isoformat()
                ollama_models.append({
                    "name": f"{clean_id}:latest",
                    "model": f"{clean_id}:latest",
                    "modified_at": iso_time,
                    "size": int(m.get("size_gb", 4.0) * (1024**3)),
                    "digest": clean_id,
                    "details": {
                        "parent_model": "",
                        "format": "gguf",
                        "family": m.get("arch", "llama"),
                        "families": [m.get("arch", "llama")],
                        "parameter_size": f"{m.get('total_layers', 32)}L",
                        "quantization_level": m.get("quant", "Q4_K_M")
                    }
                })

            resp = json.dumps({"models": ollama_models}, ensure_ascii=False).encode("utf-8")
            self._send_json_response(200, resp)
            return

        # 4. Basit Sağlık Denetimi
        if clean_path in ("", "/health"):
            resp = b'{"status": "ok", "service": "Tray-AI Gateway (OpenAI & Ollama Dual Protocol)"}'
            self._send_json_response(200, resp)
            return

        self._proxy_request("GET")

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len > 0 else b""

        parsed = urlparse(self.path)
        clean_path = parsed.path.rstrip("/").lower()

        # Ollama /api/show (Model detayları)
        if clean_path in ("/api/show", "/show"):
            try:
                p_data = json.loads(body.decode("utf-8")) if body else {}
                m_name = p_data.get("name", p_data.get("model", ""))
                if m_name.endswith(":latest"):
                    m_name = m_name[:-7]
                
                resp = json.dumps({
                    "modelfile": f"# Modelfile for {m_name}\nFROM {m_name}",
                    "parameters": "temperature 0.7\ntop_p 0.9",
                    "template": "{{ .Prompt }}",
                    "details": {"format": "gguf", "family": "llama"}
                }).encode("utf-8")
                self._send_json_response(200, resp)
                return
            except Exception:
                pass

        # Ollama /api/chat ve /api/generate İstekleri
        if clean_path in ("/api/chat", "/api/generate"):
            self._handle_ollama_inference(clean_path, body)
            return

        # OpenAI /v1/chat/completions ve /v1/completions İstekleri
        if clean_path in ("/v1/chat/completions", "/chat/completions", "/v1/completions", "/completions"):
            self._handle_openai_inference(clean_path, body)
            return

        self._proxy_request("POST", body)

    def _handle_ollama_inference(self, path, body):
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            payload = {}

        raw_model = payload.get("model", "")
        model_name = raw_model[:-7] if raw_model.endswith(":latest") else raw_model
        is_stream = payload.get("stream", True)

        # Modeli gerekirse otomatik yüklet
        self._ensure_model_loaded(model_name)

        upstream_port = self.server.gateway_ref.upstream_port
        iso_now = datetime.now(timezone.utc).isoformat()

        # Ollama formatını OpenAI formatına dönüştür
        if path == "/api/generate":
            prompt_text = payload.get("prompt", "")
            openai_payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt_text}],
                "stream": is_stream
            }
        else:
            openai_payload = {
                "model": model_name,
                "messages": payload.get("messages", []),
                "stream": is_stream
            }

        # İsteğe bağlı sampling parametrelerini aktar
        options = payload.get("options", {})
        if "temperature" in options: openai_payload["temperature"] = options["temperature"]
        if "top_p" in options: openai_payload["top_p"] = options["top_p"]
        if "top_k" in options: openai_payload["top_k"] = options["top_k"]

        upstream_url = f"http://127.0.0.1:{upstream_port}/v1/chat/completions"

        if is_stream:
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self._send_cors_headers()
            self.end_headers()

            try:
                resp = requests.post(upstream_url, json=openai_payload, stream=True, timeout=300)
                for line in resp.iter_lines():
                    if not line:
                        continue
                    line_str = line.decode("utf-8").strip()
                    if line_str.startswith("data: "):
                        data_part = line_str[6:]
                        if data_part == "[DONE]":
                            break
                        try:
                            chunk_obj = json.loads(data_part)
                            delta_content = chunk_obj.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if delta_content:
                                if path == "/api/generate":
                                    nd_chunk = {"model": raw_model, "created_at": iso_now, "response": delta_content, "done": False}
                                else:
                                    nd_chunk = {"model": raw_model, "created_at": iso_now, "message": {"role": "assistant", "content": delta_content}, "done": False}
                                self.wfile.write((json.dumps(nd_chunk, ensure_ascii=False) + "\n").encode("utf-8"))
                                self.wfile.flush()
                        except Exception:
                            pass

                # Bitiş paketi (done: true)
                if path == "/api/generate":
                    done_chunk = {"model": raw_model, "created_at": iso_now, "response": "", "done": True, "total_duration": 1000000}
                else:
                    done_chunk = {"model": raw_model, "created_at": iso_now, "message": {"role": "assistant", "content": ""}, "done": True, "total_duration": 1000000}
                self.wfile.write((json.dumps(done_chunk, ensure_ascii=False) + "\n").encode("utf-8"))
                self.wfile.flush()
            except Exception as e:
                pass
        else:
            # Stream kapalıysa tek seferde JSON dön
            try:
                resp = requests.post(upstream_url, json=openai_payload, timeout=300)
                res_data = resp.json()
                content = res_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if path == "/api/generate":
                    out_obj = {"model": raw_model, "created_at": iso_now, "response": content, "done": True}
                else:
                    out_obj = {"model": raw_model, "created_at": iso_now, "message": {"role": "assistant", "content": content}, "done": True}
                self._send_json_response(200, json.dumps(out_obj, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self._send_error(500, f"Ollama çıkarım hatası: {e}")

    def _handle_openai_inference(self, path, body):
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
            requested_model = payload.get("model", "")
            if requested_model.endswith(":latest"):
                requested_model = requested_model[:-7]
            self._ensure_model_loaded(requested_model)
        except Exception:
            pass
        self._proxy_request("POST", body)

    def _ensure_model_loaded(self, requested_model):
        active_id = self.server.gateway_ref.get_active_model_id_callback()
        upstream_port = self.server.gateway_ref.upstream_port
        is_ready = self._check_engine_ready(upstream_port)

        if (requested_model and requested_model != active_id) or not is_ready:
            self.server.gateway_ref.log_signal.emit(f"🔄 Model Hazırlanıyor: {requested_model}")
            self.server.gateway_ref.sig_switch_model.emit(requested_model)
            
            # Model hazır olana kadar bekle
            start_t = time.time()
            time.sleep(1.0)
            while time.time() - start_t < 90:
                if self._check_engine_ready(upstream_port):
                    return
                time.sleep(0.5)

    def _check_engine_ready(self, port):
        try:
            r = requests.get(f"http://127.0.0.1:{port}/health", timeout=0.4)
            return r.status_code == 200 and r.json().get("status") == "ok"
        except Exception:
            return False

    def _proxy_request(self, method, body=None):
        upstream_port = self.server.gateway_ref.upstream_port
        upstream_url = f"http://127.0.0.1:{upstream_port}{self.path}"

        headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length")}
        try:
            resp = requests.request(
                method=method,
                url=upstream_url,
                data=body,
                headers=headers,
                stream=True,
                timeout=300
            )

            self.send_response(resp.status_code)
            for k, v in resp.headers.items():
                if k.lower() not in ("content-length", "transfer-encoding", "content-encoding"):
                    self.send_header(k, v)
            self._send_cors_headers()
            self.end_headers()

            for chunk in resp.iter_content(chunk_size=512):
                if chunk:
                    try:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        # İstemci soketi kapattı, aktarımı sessizce sonlandır
                        return

        except (BrokenPipeError, ConnectionResetError):
            return
        except requests.exceptions.ConnectionError:
            try:
                self._send_error(503, "Lokal motor hazırlanıyor veya model henüz yüklenmedi...")
            except Exception:
                pass
        except Exception as e:
            try:
                self._send_error(500, f"Gateway Hatası: {str(e)}")
            except Exception:
                pass

    def _send_json_response(self, code, data_bytes):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data_bytes)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(data_bytes)

    def _send_error(self, code, msg):
        err_body = json.dumps({"error": {"message": msg, "code": code}}).encode("utf-8")
        self._send_json_response(code, err_body)


class APIGatewayServer(QThread):
    log_signal = pyqtSignal(str)
    sig_switch_model = pyqtSignal(str)

    def __init__(self, host="0.0.0.0", port=8080, upstream_port=8081,
                 get_all_models_func=None, get_active_model_id_func=None):
        super().__init__()
        self.host = host
        self.port = port
        self.upstream_port = upstream_port
        self.get_all_models_callback = get_all_models_func or (lambda: [])
        self.get_active_model_id_callback = get_active_model_id_func or (lambda: "")
        self.httpd = None

    def run(self):
        try:
            self.httpd = ThreadingHTTPServer((self.host, self.port), GatewayRequestHandler)
            self.httpd.gateway_ref = self
            self.log_signal.emit(f"🌐 Hibrit Gateway Aktif (OpenAI + Ollama): http://{self.host}:{self.port}")
            self.httpd.serve_forever()
        except Exception as e:
            self.log_signal.emit(f"⚠️ Gateway Başlatılamadı: {e}")

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()

```

## Dosya: core/cache_manager.py
```python
import sqlite3
import os
import json

CACHE_SCHEMA_VERSION = 3

class CacheManager:
    def __init__(self, db_path=os.path.expanduser("~/.config/tray-ai/models_cache.db")):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA user_version")
            ver = cursor.fetchone()[0]
            if ver != CACHE_SCHEMA_VERSION:
                cursor.execute("DROP TABLE IF EXISTS models")
                cursor.execute(f"PRAGMA user_version = {CACHE_SCHEMA_VERSION}")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    path TEXT PRIMARY KEY,
                    filename TEXT,
                    size_gb REAL,
                    mtime REAL,
                    arch TEXT,
                    quant TEXT,
                    max_context INTEGER,
                    total_layers INTEGER,
                    has_mtp INTEGER,
                    has_thinking INTEGER,
                    has_tools INTEGER,
                    has_vision INTEGER,
                    extra_meta TEXT
                )
            """)
            conn.commit()

    def _row_to_dict(self, row):
        extra = json.loads(row[12]) if row[12] else {}
        return {
            "path": row[0],
            "filename": row[1],
            "size_gb": row[2],
            "mtime": row[3],
            "arch": row[4],
            "quant": row[5],
            "max_context": row[6],
            "base_context": extra.get("base_context", row[6]),
            "total_layers": row[7],
            "has_mtp": bool(row[8]),
            "mtp_layers": extra.get("mtp_layers", 1 if row[8] else 0),
            "has_yarn": extra.get("has_yarn", False),
            "has_thinking": bool(row[9]),
            "has_tools": bool(row[10]),
            "has_vision": bool(row[11]),
            "publisher": extra.get("publisher", "Bilinmiyor"),
            "recommended_temp": extra.get("recommended_temp", 0.70),
            "recommended_topp": extra.get("recommended_topp", 0.90),
            "recommended_minp": extra.get("recommended_minp", 0.05),
            " recommended_top_k": extra.get("recommended_top_k", 40),
            "extra_meta": extra
        }

    def get_model(self, path, current_mtime):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM models WHERE path = ? AND mtime = ?", (path, current_mtime))
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(row)
        return None

    def save_model(self, info):
        extra = info.get("extra_meta", {}).copy()
        extra["publisher"] = info.get("publisher", "Bilinmiyor")
        extra["base_context"] = info.get("base_context", info.get("max_context", 4096))
        extra["mtp_layers"] = info.get("mtp_layers", 0)
        extra["has_yarn"] = info.get("has_yarn", False)
        extra["recommended_temp"] = info.get("recommended_temp", 0.70)
        extra["recommended_topp"] = info.get("recommended_topp", 0.90)
        extra["recommended_minp"] = info.get("recommended_minp", 0.05)
        extra["recommended_top_k"] = info.get("recommended_top_k", 40)

        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO models VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                info["path"], info["filename"], info["size_gb"], info["mtime"],
                info["arch"], info["quant"], info["max_context"], info["total_layers"],
                int(info["has_mtp"]), int(info["has_thinking"]), int(info["has_tools"]),
                int(info["has_vision"]), json.dumps(extra)
            ))
            conn.commit()

    def get_all_cached_models(self):
        results = []
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM models")
            for row in cursor.fetchall():
                results.append(self._row_to_dict(row))
        return results

    def get_all_by_folder(self, folder):
        results = []
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM models WHERE path LIKE ?", (f"{folder}%",))
            for row in cursor.fetchall():
                results.append(self._row_to_dict(row))
        return results

```

## Dosya: core/engine_updater.py
```python
import os
import re
import shutil
import zipfile
import tarfile
import requests
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal

class EngineVersionChecker(QThread):
    version_info_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, engines_dir):
        super().__init__()
        self.engines_dir = engines_dir

    def get_local_version(self, bin_name):
        bin_path = os.path.join(self.engines_dir, bin_name)
        if not os.path.exists(bin_path):
            return "Kurulu Değil"
        try:
            env = os.environ.copy()
            env["LD_LIBRARY_PATH"] = f"{self.engines_dir}:{env.get('LD_LIBRARY_PATH', '')}"
            out = subprocess.check_output(
                [bin_path, "--version"],
                stderr=subprocess.STDOUT,
                text=True,
                timeout=3,
                env=env
            )
            # Yeni format: version: 0.7.0-dev (build 1, commit df9beac)
            m_new = re.search(r"version:\s*([^\s(]+)\s*\((?:build\s*(\d+),?\s*)?(?:commit\s*)?([a-f0-9]+)\)", out)
            if m_new:
                ver_tag = m_new.group(1)
                build_num = m_new.group(2)
                commit_hash = m_new.group(3)
                if build_num and int(build_num) > 1:
                    return f"b{build_num} ({commit_hash})"
                return f"v{ver_tag} ({commit_hash})"

            # Eski format: version: 4850 (df9beac)
            m_old = re.search(r"version:\s*(\d+)\s*\(([a-f0-9]+)\)", out)
            if m_old:
                return f"b{m_old.group(1)} ({m_old.group(2)})"

            m2 = re.search(r"b(\d{4,5})", out)
            if m2:
                return f"b{m2.group(1)}"
            return "Kurulu (Aktif)"
        except Exception:
            return "Kurulu (.so hazır)"

    def run(self):
        info = {
            "local_main": self.get_local_version("llama-server"),
            
            "latest_tag": "Bilinmiyor",
            "published_at": "",
            "release_notes": "",
            "assets": {},
            "has_vulkan": shutil.which("vulkaninfo") is not None or os.path.exists("/usr/include/vulkan/vulkan.h"),
            "has_rocm": os.path.exists("/opt/rocm"),
            "has_cuda": shutil.which("nvcc") is not None
        }

        try:
            headers = {"User-Agent": "TrayAI-Updater/2.0"}
            r = requests.get("https://api.github.com/repos/ggml-org/llama.cpp/releases/latest", headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                info["latest_tag"] = data.get("tag_name", "Latest")
                info["published_at"] = data.get("published_at", "")[:10]
                info["release_notes"] = (data.get("body", "") or "")[:300]

                for asset in data.get("assets", []):
                    aname = asset.get("name", "").lower()
                    if "linux" in aname or "ubuntu" in aname:
                        size_mb = round(asset.get("size", 0) / (1024 * 1024), 2)
                        url = asset.get("browser_download_url", "")
                        if "vulkan" in aname:
                            info["assets"]["vulkan"] = {"url": url, "size_mb": size_mb, "name": asset["name"]}
                        elif "rocm" in aname or "hip" in aname:
                            info["assets"]["rocm"] = {"url": url, "size_mb": size_mb, "name": asset["name"]}
                        elif "cuda" in aname:
                            info["assets"]["cuda"] = {"url": url, "size_mb": size_mb, "name": asset["name"]}
                        else:
                            info["assets"]["cpu"] = {"url": url, "size_mb": size_mb, "name": asset["name"]}
        except Exception as e:
            self.error_occurred.emit(str(e))

        self.version_info_ready.emit(info)


class EngineUpdateWorker(QThread):
    progress_msg = pyqtSignal(int, str)
    finished_ok = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, engines_dir, target_type="vulkan", mode="build", asset_url="",
                 turbo_repo="https://github.com/ggml-org/llama.cpp.git", turbo_branch=""):
        super().__init__()
        self.engines_dir = os.path.abspath(engines_dir)
        self.target_type = target_type  # "vulkan", "cpu", "rocm", "cuda"
        self.mode = mode  # "download" veya "build"
        self.asset_url = asset_url
        self.turbo_repo = turbo_repo.strip() or "https://github.com/ggml-org/llama.cpp.git"
        self.turbo_branch = turbo_branch.strip()

    def run(self):
        try:
            os.makedirs(self.engines_dir, exist_ok=True)
            # TurboQuant her zaman kaynak koddan veya kendi özel deposundan derlenir ki llama-server-turboquant olarak çıksın
            if self.mode == "build" or not self.asset_url:
                self._build_from_source()
            else:
                self._download_and_extract()
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _download_and_extract(self):
        dest_bin_name = "llama-server"
        self.progress_msg.emit(10, f"GitHub'dan {self.target_type.upper()} paketi indiriliyor -> {dest_bin_name}...")
        tmp_archive = "/tmp/llama_engine_pkg"
        r = requests.get(self.asset_url, stream=True, timeout=30)
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        downloaded = 0

        with open(tmp_archive, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 512):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = 10 + int((downloaded / total) * 65)
                        self.progress_msg.emit(pct, f"İndiriliyor ({dest_bin_name})... ({downloaded // (1024*1024)} / {total // (1024*1024)} MB)")

        self.progress_msg.emit(80, f"Arşiv açılıyor, {dest_bin_name} ve .so kütüphaneleri yerleştiriliyor...")
        extract_dir = "/tmp/llama_extracted"
        shutil.rmtree(extract_dir, ignore_errors=True)
        os.makedirs(extract_dir, exist_ok=True)

        if self.asset_url.endswith(".zip"):
            with zipfile.ZipFile(tmp_archive, "r") as z:
                z.extractall(extract_dir)
        else:
            with tarfile.open(tmp_archive, "r:*") as t:
                t.extractall(extract_dir)

        found_server = False
        for root, _, files in os.walk(extract_dir):
            for file in files:
                full_p = os.path.join(root, file)
                if file == "llama-server":
                    shutil.copy2(full_p, os.path.join(self.engines_dir, dest_bin_name))
                    os.chmod(os.path.join(self.engines_dir, dest_bin_name), 0o755)
                    found_server = True
                elif ".so" in file:
                    shutil.copy2(full_p, os.path.join(self.engines_dir, file))

        shutil.rmtree(extract_dir, ignore_errors=True)
        if os.path.exists(tmp_archive):
            os.remove(tmp_archive)

        if not found_server:
            raise RuntimeError("Pakette llama-server bulunamadı!")

        self.progress_msg.emit(100, f"✅ {dest_bin_name} ve .so dosyaları başarıyla güncellendi!")
        self.finished_ok.emit(self.target_type)

    def _build_from_source(self):
        dest_bin_name = "llama-server"
        build_dir = "/tmp/tray_ai_llama_build"
        shutil.rmtree(build_dir, ignore_errors=True)

        repo_url = getattr(self, "turbo_repo", None) or "https://github.com/ggml-org/llama.cpp.git"

        # Eğer yerel bir klasör yolu verildiyse (örn: /home/anonymous/turboquant-llama.cpp) doğrudan oradan kopyala/derle
        if os.path.isdir(repo_url):
            self.progress_msg.emit(15, f"Yerel kaynak klasörü kopyalanıyor: {repo_url}...")
            shutil.copytree(repo_url, build_dir, symlinks=True)
        else:
            self.progress_msg.emit(10, f"Kaynak kod çekiliyor ({repo_url}) -> Hedef: {dest_bin_name}...")
            clone_cmd = ["git", "clone", "--depth", "1", "--tags"]
            if getattr(self, "turbo_branch", None):
                clone_cmd.extend(["-b", self.turbo_branch])
            clone_cmd.extend([repo_url, build_dir])
            subprocess.run(clone_cmd, check=True)

        cmake_args = [
            "cmake", "-B", "build",
            "-DBUILD_SHARED_LIBS=ON",
            "-DCMAKE_INSTALL_RPATH=$ORIGIN",
            "-DCMAKE_BUILD_WITH_INSTALL_RPATH=ON",
            "-DLLAMA_CURL=ON",
            "-DGGML_NATIVE=ON"
        ]

        if self.target_type == "vulkan":
            cmake_args.append("-DGGML_VULKAN=ON")
        elif self.target_type == "rocm":
            cmake_args.append("-DGGML_HIP=ON")
        elif self.target_type == "cuda":
            cmake_args.append("-DGGML_CUDA=ON")

        self.progress_msg.emit(35, f"CMake yapılandırılıyor ({dest_bin_name} + Vulkan + .so RPATH)...")
        subprocess.run(cmake_args, cwd=build_dir, check=True)

        cores = str(os.cpu_count() or 4)
        self.progress_msg.emit(60, f"🔨 {dest_bin_name} {cores} çekirdek ile derleniyor...")
        subprocess.run(
            ["cmake", "--build", "build", "--config", "Release", "--target", "llama-server", f"-j{cores}"],
            cwd=build_dir,
            check=True
        )

        # Derlenen ikiliyi tam olarak seçilen hedef adıyla (llama-server-turboquant veya llama-server) kaydet!
        built_bin = os.path.join(build_dir, "build", "bin", "llama-server")
        if not os.path.exists(built_bin):
            for r, _, f_list in os.walk(os.path.join(build_dir, "build")):
                if "llama-server" in f_list and not os.path.islink(os.path.join(r, "llama-server")):
                    built_bin = os.path.join(r, "llama-server")
                    break
        if not os.path.exists(built_bin):
            raise FileNotFoundError("Derleme sonrası llama-server ikili dosyası bulunamadı!")

        final_dest = os.path.join(self.engines_dir, dest_bin_name)
        shutil.copy2(built_bin, final_dest)
        os.chmod(final_dest, 0o755)

        # Üretilen tüm .so kütüphanelerini (sembolik linkleriyle birlikte) engines/ klasörüne kopyala
        bin_dir = os.path.join(build_dir, "build", "bin")
        for root, _, files in os.walk(os.path.join(build_dir, "build")):
            for file in files:
                if ".so" in file:
                    src_so = os.path.join(root, file)
                    dst_so = os.path.join(self.engines_dir, file)
                    try:
                        if os.path.exists(dst_so) or os.path.islink(dst_so):
                            os.remove(dst_so)
                        shutil.copy2(src_so, dst_so, follow_symlinks=False)
                    except Exception:
                        pass

        shutil.rmtree(build_dir, ignore_errors=True)
        self.progress_msg.emit(100, f"✅ {dest_bin_name} ve tüm .so kütüphaneleri engines/ içine başarıyla kuruldu!")
        self.finished_ok.emit(self.target_type)

```

## Dosya: core/gguf_parser.py
```python
import os
import re
from gguf import GGUFReader

def extract_scalar(field):
    if not field or not hasattr(field, "parts") or len(field.parts) == 0:
        return None
    val = field.parts[-1]
    if isinstance(val, (bytes, bytearray)):
        return val.decode("utf-8", errors="ignore").strip("\x00")
    if hasattr(val, "tolist"):
         data = val.tolist()
         if isinstance(data, list):
             if len(data) == 1:
                 return data[0]
             if len(data) <= 32 and all(isinstance(x, int) and 0 <= x < 256 for x in data):
                 try:
                     return bytes(data).decode("utf-8", errors="ignore").strip("\x00")
                 except:
                     pass
             return f"[Array: {len(data)} items]"
         return data
    if isinstance(val, (list, tuple)) and len(val) > 0:
        return val[0]
    return val

def detect_publisher(file_path, all_kv, general_name):
    for key in ["general.organization", "general.author", "general.base_model.0.organization", "general.base_model.author", "quantize.author"]:
        if key in all_kv and str(all_kv[key]).strip():
            return str(all_kv[key]).strip()

    path_low = file_path.lower()
    known_publishers = [
        "unsloth", "bartowski", "thebloke", "mradermacher", "lmstudio-community",
        "qwen", "deepseek-ai", "meta-llama", "mistralai", "google", "microsoft", "xiaomi"
    ]
    for pub in known_publishers:
        if f"/{pub}/" in path_low or f"_{pub}_" in path_low or path_low.endswith(f"-{pub}.gguf"):
            return pub.capitalize()
        if pub in os.path.basename(file_path).lower():
            return pub.capitalize()

    if general_name and "/" in general_name:
        return general_name.split("/")[0].strip()

    return "Bilinmiyor"

def infer_optimal_samplers(filename, arch, general_name, has_thinking, kv_temp, kv_topp, kv_minp, kv_topk):
    """
    LM Studio ve Unsloth Studio gibi hem GGUF KV içindeki gömülü sampling
    değerlerini okur hem de modelin resmi profilinden (Qwen3, DeepSeek-R1,
    Coder, Gemma-3, Llama-3) en doğru sıcaklık / Top-P / Min-P değerlerini çıkarır.
    """
    fn_low = (filename + " " + general_name).lower()
    arch_low = arch.lower()

    # 1. Varsayılan başlangıç değerleri
    temp = 0.70
    top_p = 0.90
    min_p = 0.05
    top_k = 40
    source = "Standart Profil"

    # 2. Model ailesine göre Unsloth / Resmi Model Kartı profilleri
    if "qwen3" in fn_low or "qwen3" in arch_low or "qwq" in fn_low:
        if has_thinking or "thinking" in fn_low or "qwq" in fn_low:
            temp, top_p, min_p, top_k = 0.60, 0.95, 0.00, 20
            source = "Qwen3 Thinking Resmi Profili"
        elif "coder" in fn_low:
            temp, top_p, min_p, top_k = 0.20, 0.80, 0.05, 20
            source = "Qwen Coder Resmi Profili"
        else:
            temp, top_p, min_p, top_k = 0.70, 0.80, 0.00, 20
            source = "Qwen3 Instruct Resmi Profili"
    elif any(k in fn_low for k in ["deepseek-r1", "r1-", "-r1", "deepseek-v3", "deepseek2"]):
        temp, top_p, min_p, top_k = 0.60, 0.95, 0.05, 40
        source = "DeepSeek R1/V3 Resmi Profili"
    elif "gemma-3" in fn_low or "gemma3" in arch_low or "gemma2" in arch_low:
        temp, top_p, min_p, top_k = 1.00, 0.95, 0.01, 64
        source = "Google Gemma-3 Resmi Profili"
    elif any(k in fn_low for k in ["coder", "codestral", "starcoder", "devstral", "qwen2.5-coder"]):
        temp, top_p, min_p, top_k = 0.20, 0.90, 0.05, 40
        source = "Kodlama (Coder) Hassas Profili"
    elif "mistral" in fn_low or "ministral" in fn_low or "nemo" in fn_low:
        temp, top_p, min_p, top_k = 0.30, 0.95, 0.05, 40
        source = "Mistral Resmi Profili"
    elif "llama-3" in fn_low or "llama3" in fn_low:
        temp, top_p, min_p, top_k = 0.60, 0.90, 0.05, 40
        source = "Llama-3 Resmi Profili"
    elif has_thinking:
        temp, top_p, min_p, top_k = 0.60, 0.95, 0.05, 40
        source = "Reasoning (Akıl Yürütme) Profili"

    # 3. Eğer GGUF dosyası içine açıkça sampling metadatası gömülmüşse onu önceliklendir
    if kv_temp is not None:
        temp = round(float(kv_temp), 2)
        source = "GGUF Gömülü Metadata"
    if kv_topp is not None:
        top_p = round(float(kv_topp), 2)
    if kv_minp is not None:
        min_p = round(float(kv_minp), 2)
    if kv_topk is not None:
        top_k = int(kv_topk)

    return temp, top_p, min_p, top_k, source

def analyze_gguf_file(file_path):
    info = {
        "path": file_path,
        "filename": os.path.basename(file_path),
        "size_gb": round(os.path.getsize(file_path) / (1024**3), 2),
        "mtime": os.path.getmtime(file_path),
        "arch": "llama",
        "quant": "Bilinmiyor",
        "publisher": "Bilinmiyor",
        "max_context": 4096,
        "base_context": 4096,
        "total_layers": 32,
        "has_mtp": False,
        "mtp_layers": 0,
        "has_yarn": False,
        "has_thinking": False,
        "has_tools": False,
        "has_vision": False,
        "recommended_temp": 0.70,
        "recommended_topp": 0.90,
        "recommended_minp": 0.05,
        "recommended_top_k": 40,
        "extra_meta": {
            "general_name": "",
            "sampler_source": "Standart Profil",
            "rope_freq_base": 10000.0,
            "rope_scale": 1.0,
            "rope_scaling_type": "none",
            "yarn_orig_ctx": 0,
            "yarn_ext_factor": 1.0,
            "embed_length": 4096,
            "feed_forward_length": 11008,
            "head_count": 32,
            "head_count_kv": 8,
            "key_length": 128,
            "value_length": 128,
            "expert_count": 0,
            "expert_used_count": 0,
            "bos_token_id": -1,
            "eos_token_id": -1,
            "chat_template": "",
            "tensor_count": 0,
            "mtp_reason": "",
            "yarn_reason": "",
            "all_kv": {}
        }
    }
    
    try:
        reader = GGUFReader(file_path)
        info["extra_meta"]["tensor_count"] = len(reader.tensors)

        arch_field = reader.fields.get("general.architecture")
        arch = extract_scalar(arch_field)
        if arch:
            info["arch"] = str(arch).lower()

        template_str = ""
        all_kv = {}
        kv_temp = None
        kv_topp = None
        kv_minp = None
        kv_topk = None

        for key, field in reader.fields.items():
            k_low = key.lower()
            val = extract_scalar(field)
            
            if val is not None:
                s_val = str(val)
                if len(s_val) > 400 and k_low != "tokenizer.chat_template":
                    all_kv[key] = s_val[:400] + "... (truncated)"
                elif k_low != "tokenizer.chat_template":
                    all_kv[key] = s_val

            if k_low == "general.name" and val:
                info["extra_meta"]["general_name"] = str(val)
            elif k_low.endswith(".context_length") and isinstance(val, (int, float)):
                info["max_context"] = int(val)
                info["base_context"] = int(val)
            elif k_low.endswith(".block_count") and isinstance(val, (int, float)):
                info["total_layers"] = int(val)
            elif k_low.endswith(".rope.freq_base") and isinstance(val, (int, float)):
                info["extra_meta"]["rope_freq_base"] = float(val)
            elif (k_low.endswith(".rope.scale_linear") or k_low.endswith(".rope.scaling.factor")) and isinstance(val, (int, float)):
                info["extra_meta"]["rope_scale"] = float(val)
            elif k_low.endswith(".rope.scaling.type") and val:
                info["extra_meta"]["rope_scaling_type"] = str(val).lower()
                if any(y in str(val).lower() for y in ["yarn", "linear", "dynamic", "longrope"]):
                    info["has_yarn"] = True
                    info["extra_meta"]["yarn_reason"] = f"GGUF scaling.type={val}"
            elif k_low.endswith(".rope.scaling.original_context_length") and isinstance(val, (int, float)):
                info["extra_meta"]["yarn_orig_ctx"] = int(val)
                info["has_yarn"] = True
                info["extra_meta"]["yarn_reason"] = f"orig_ctx={int(val)}"
            elif k_low.endswith(".embedding_length") and isinstance(val, (int, float)):
                info["extra_meta"]["embed_length"] = int(val)
            elif k_low.endswith(".feed_forward_length") and isinstance(val, (int, float)):
                info["extra_meta"]["feed_forward_length"] = int(val)
            elif k_low.endswith(".attention.head_count") and isinstance(val, (int, float)):
                info["extra_meta"]["head_count"] = int(val)
            elif k_low.endswith(".attention.head_count_kv") and isinstance(val, (int, float)):
                info["extra_meta"]["head_count_kv"] = int(val)
            elif k_low.endswith(".attention.key_length") and isinstance(val, (int, float)):
                info["extra_meta"]["key_length"] = int(val)
            elif k_low.endswith(".attention.value_length") and isinstance(val, (int, float)):
                info["extra_meta"]["value_length"] = int(val)
            elif k_low.endswith(".expert_count") and isinstance(val, (int, float)):
                info["extra_meta"]["expert_count"] = int(val)
            elif k_low.endswith(".expert_used_count") and isinstance(val, (int, float)):
                info["extra_meta"]["expert_used_count"] = int(val)
            # MTP Metadata Anahtarları (llama.cpp & Unsloth standartları)
            elif any(m_k in k_low for m_k in ["nextn_predict_layers", "num_nextn_predict_layers", "mtp_depth", "mtp_layers", "speculative_layers", "n_predict_layers"]):
                if isinstance(val, (int, float)) and val > 0:
                    info["has_mtp"] = True
                    info["mtp_layers"] = int(val)
                    info["extra_meta"]["mtp_reason"] = f"GGUF KV ({key}={int(val)})"
            # Gömülü Sampling Anahtarları
            elif any(k_low.endswith(s) for s in [".sampling.temp", ".sampling.temperature", "general.temperature", "temperature"]) and isinstance(val, (int, float)):
                kv_temp = float(val)
            elif any(k_low.endswith(s) for s in [".sampling.top_p", "general.top_p", "top_p"]) and isinstance(val, (int, float)):
                kv_topp = float(val)
            elif any(k_low.endswith(s) for s in [".sampling.min_p", "general.min_p", "min_p"]) and isinstance(val, (int, float)):
                kv_minp = float(val)
            elif any(k_low.endswith(s) for s in [".sampling.top_k", "general.top_k", "top_k"]) and isinstance(val, (int, float)):
                kv_topk = int(val)
            elif k_low == "tokenizer.chat_template" and val:
                raw_tpl = str(val)
                info["extra_meta"]["chat_template"] = raw_tpl[:4000]
                template_str = raw_tpl.lower()
            elif k_low.startswith("clip.") or k_low.startswith("vision."):
                info["has_vision"] = True

        info["extra_meta"]["all_kv"] = all_kv
        info["publisher"] = detect_publisher(file_path, all_kv, info["extra_meta"]["general_name"])

        # Head boyutu hesabı
        emb = info["extra_meta"]["embed_length"]
        hc = max(1, info["extra_meta"]["head_count"])
        if info["extra_meta"]["head_count_kv"] <= 0:
            info["extra_meta"]["head_count_kv"] = hc
        if info["extra_meta"]["key_length"] <= 0 or info["extra_meta"]["key_length"] == 128:
            info["extra_meta"]["key_length"] = emb // hc
            info["extra_meta"]["value_length"] = emb // hc

        # =====================================================================
        # DETAYLI MTP (MULTI-TOKEN PREDICTION) TENSÖR VE MİMARİ TARAMASI
        # =====================================================================
        mtp_tensor_hits = 0
        mtp_block_indices = set()
        total_blocks = info["total_layers"]

        for t in reader.tensors:
            tname = t.name.lower()
            # 1. Açık MTP / NextN / Shared Head / Enorm-Hnorm-Eh_proj tensörleri
            if any(x in tname for x in ["mtp", "nextn", "eh_proj", "shared_head", ".enorm", ".hnorm", "spec_head", "multi_token"]):
                mtp_tensor_hits += 1
                m_blk = re.search(r"blk\.(\d+)\.", tname)
                if m_blk:
                    mtp_block_indices.add(int(m_blk.group(1)))
            else:
                # 2. Normal block_count sayısını aşan ekstra tahmin katmanı var mı? (Örn: 61 katmanlı modelde blk.61.*)
                m_blk = re.search(r"^blk\.(\d+)\.", tname)
                if m_blk and int(m_blk.group(1)) >= total_blocks:
                    mtp_block_indices.add(int(m_blk.group(1)))

            if "mmproj" in tname or "vision" in tname or "vpm." in tname:
                info["has_vision"] = True

        if mtp_tensor_hits > 0 or len(mtp_block_indices) > 0:
            info["has_mtp"] = True
            if info["mtp_layers"] <= 0:
                info["mtp_layers"] = max(1, len(mtp_block_indices) if mtp_block_indices else 1)
            if not info["extra_meta"]["mtp_reason"]:
                info["extra_meta"]["mtp_reason"] = f"Tensör Tablosu ({mtp_tensor_hits} MTP tensörü)"

        # Mimari / Model Ailesi Bazlı MTP Tespiti (DeepSeek-V3/R1, MiMo, Qwen3-MoE, GLM-4.5)
        fn_and_name = (info["filename"] + " " + info["extra_meta"]["general_name"]).lower()
        arch_low = info["arch"].lower()
        if not info["has_mtp"]:
            if any(k in fn_and_name for k in ["mtp", "nextn", "deepseek-v3", "deepseek-r1-0528", "mimo-", "glm-4.5"]) or arch_low in ("deepseek2", "mimo", "qwen3moe"):
                info["has_mtp"] = True
                info["mtp_layers"] = max(1, info["mtp_layers"] or 1)
                info["extra_meta"]["mtp_reason"] = f"Mimari MTP Desteği ({info['arch'].upper()})"

        # =====================================================================
        # DETAYLI YaRN VE UZUN BAĞLAM (CONTEXT EXTENSION) TESPİTİ
        # =====================================================================
        rope_base = info["extra_meta"]["rope_freq_base"]
        if info["extra_meta"]["rope_scale"] > 1.0:
            info["has_yarn"] = True
            if not info["extra_meta"]["yarn_reason"]:
                info["extra_meta"]["yarn_reason"] = f"rope_scale={info['extra_meta']['rope_scale']}"
        elif arch_low in ("qwen2", "qwen2moe", "qwen3", "qwen3moe", "deepseek2", "llama", "mistral", "gemma2", "gemma3") and (rope_base >= 100000.0 or info["max_context"] >= 32768):
            # Qwen, Llama-3, DeepSeek ve Gemma modelleri yüksek RoPE base ile YaRN genişletmesini doğal destekler
            info["has_yarn"] = True
            if not info["extra_meta"]["yarn_reason"]:
                info["extra_meta"]["yarn_reason"] = f"Yüksek RoPE Base ({int(rope_base):,}) & YaRN Uyumlu Mimari"

        # Quant Tespiti
        fn_up = info["filename"].upper()
        for q in [
            "Q8_0", "Q6_K_XL", "Q6_K_L", "Q6_K", "Q5_K_XL", "Q5_K_L", "Q5_K_M", "Q5_K_S",
            "Q4_K_XL", "Q4_K_L", "Q4_K_M", "Q4_K_S", "Q4_0", "IQ4_XS", "IQ4_NL",
            "Q3_K_XL", "Q3_K_L", "Q3_K_M", "IQ3_M", "IQ3_XXS", "Q2_K_L", "Q2_K", "BF16", "F16"
        ]:
            if q in fn_up:
                info["quant"] = q
                break

        # Thinking / Tools / Vision Tespiti
        fn_low = info["filename"].lower()
        if template_str:
            if any(w in template_str for w in ["<think>", "thought", "reasoning", "think_start", "enable_thinking"]):
                info["has_thinking"] = True
            if any(w in template_str for w in ["tools", "tool_call", "<tool_call>", "function", "mcp"]):
                info["has_tools"] = True

        if any(w in fn_and_name for w in ["qwen3", "qwq", "r1", "thinking", "reasoning", "deepseek", "marco-o1", "s1-", "qwq-"]):
            info["has_thinking"] = True
        if any(w in fn_and_name for w in ["vl", "vision", "llava", "pixtral", "minicpm-v", "gemma-3-4b", "gemma-3-12b", "gemma-3-27b"]):
            info["has_vision"] = True
        if any(w in fn_and_name for w in ["instruct", "coder", "qwen", "llama-3", "mistral", "gemma", "hermes", "tool"]):
            info["has_tools"] = True

        # Akıllı Sıcaklık, Top-P, Min-P, Top-K Çıkarımı
        t_val, tp_val, mp_val, tk_val, s_src = infer_optimal_samplers(
            info["filename"], info["arch"], info["extra_meta"]["general_name"],
            info["has_thinking"], kv_temp, kv_topp, kv_minp, kv_topk
        )
        info["recommended_temp"] = t_val
        info["recommended_topp"] = tp_val
        info["recommended_minp"] = mp_val
        info["recommended_top_k"] = tk_val
        info["extra_meta"]["sampler_source"] = s_src

    except Exception as e:
        print(f"GGUF Okuma Hatası ({file_path}): {e}")

    return info

def estimate_memory_usage_gb(model_info, ctx_len, ngl, cache_k_type="f16", cache_v_type="f16"):
    if not model_info:
        return {"total_gb": 0.0, "vram_gb": 0.0, "ram_gb": 0.0, "kv_gb": 0.0}

    size_gb = model_info.get("size_gb", 4.0)
    total_layers = max(1, model_info.get("total_layers", 32))
    extra = model_info.get("extra_meta", {})
    n_head_kv = max(1, extra.get("head_count_kv", 8))
    k_dim = max(64, extra.get("key_length", 128))
    v_dim = max(64, extra.get("value_length", 128))

    bytes_per_elem = {
        "f16": 2.0, "bf16": 2.0, "q8_0": 1.05,
        "q5_1": 0.70, "q5_0": 0.65, "q4_1": 0.55, "q4_0": 0.52, "iq4_nl": 0.52
    }
    b_k = bytes_per_elem.get(cache_k_type, 2.0)
    b_v = bytes_per_elem.get(cache_v_type, 2.0)

    kv_bytes = ctx_len * total_layers * n_head_kv * ((k_dim * b_k) + (v_dim * b_v))
    kv_gb = round(kv_bytes / (1024**3), 2)
    compute_gb = 0.35 + (ctx_len / 65536.0) * 0.45

    gpu_ratio = min(1.0, max(0.0, ngl / float(total_layers)))
    vram_model = size_gb * gpu_ratio
    ram_model = size_gb * (1.0 - gpu_ratio)

    vram_total = round(vram_model + (kv_gb if gpu_ratio > 0 else 0.0) + (compute_gb if gpu_ratio > 0 else 0.0), 2)
    ram_total = round(ram_model + (0.0 if gpu_ratio > 0 else kv_gb + compute_gb), 2)
    total_gb = round(size_gb + kv_gb + compute_gb, 2)

    return {
        "total_gb": total_gb,
        "vram_gb": vram_total,
        "ram_gb": ram_total,
        "kv_gb": kv_gb
    }

```

## Dosya: core/hardware.py
```python
import psutil
import subprocess
import os
import re

def get_system_hardware(engine_bin_path=None):
    ram = psutil.virtual_memory()
    total_ram_gb = round(ram.total / (1024**3), 2)
    
    cpu_name = "Bilinmeyen İşlemci"
    cpu_arch = os.uname().machine
    cpu_flags = []
    try:
        with open("/proc/cpuinfo", "r") as f:
            content = f.read()
            for line in content.splitlines():
                if "model name" in line and cpu_name == "Bilinmeyen İşlemci":
                    cpu_name = line.split(":")[1].strip()
                if "flags" in line and not cpu_flags:
                    flags_raw = line.split(":")[1].strip().split()
                    for flag in ["avx512f", "avx2", "avx", "fma", "f16c"]:
                        if flag in flags_raw:
                            cpu_flags.append(flag.upper().replace("AVX512F", "AVX-512"))
    except:
        pass

    gpus = []
    seen_keys = set()

    if engine_bin_path and os.path.exists(engine_bin_path):
        try:
            eng_dir = os.path.dirname(os.path.abspath(engine_bin_path))
            env = os.environ.copy()
            env["LD_LIBRARY_PATH"] = f"{eng_dir}:{env.get('LD_LIBRARY_PATH', '')}"
            out = subprocess.check_output(
                [engine_bin_path, "--list-devices"],
                stderr=subprocess.STDOUT,
                text=True,
                timeout=4,
                cwd=eng_dir,
                env=env
            )
            for line in out.splitlines():
                # Sadece "Vulkan0: AMD..." veya "CUDA0: ..." formatındaki gerçek cihaz satırlarını al
                m = re.match(r"^\s*((?:Vulkan|ROCm|HIP|CUDA|Metal|SYCL)\d+)\s*:\s*(.+?)\s*\((\d+)\s*MiB", line, re.IGNORECASE)
                if m:
                    dev_id_str = m.group(1).strip()
                    dev_name = m.group(2).strip()
                    vram_mib = int(m.group(3))

                    idx_match = re.search(r"(\d+)$", dev_id_str)
                    dev_idx = int(idx_match.group(1)) if idx_match else len(gpus)
                    backend = re.sub(r"\d+$", "", dev_id_str)

                    # Aynı cihazın veya aynı kart isminin 2. kez eklenmesini engelle!
                    dedup_key = f"{dev_idx}_{dev_name.lower()}"
                    if dedup_key in seen_keys or dev_id_str.lower() in seen_keys:
                        continue
                    seen_keys.add(dedup_key)
                    seen_keys.add(dev_id_str.lower())

                    gpus.append({
                        "id": dev_idx,
                        "backend_id": dev_id_str,
                        "name": dev_name,
                        "vram_gb": round(vram_mib / 1024.0, 2),
                        "backend": backend
                    })
        except:
            pass

    if not gpus:
        try:
            vk_out = subprocess.check_output(["vulkaninfo", "--summary"], stderr=subprocess.DEVNULL, text=True, timeout=4)
            blocks = vk_out.split("GPU")
            for b in blocks[1:]:
                id_m = re.match(r"^(\d+)\s*:", b)
                name_m = re.search(r"deviceName\s*=\s*(.+)", b)
                type_m = re.search(r"deviceType\s*=\s*(.+)", b)
                if id_m and name_m:
                    gid = int(id_m.group(1))
                    gname = name_m.group(1).strip()
                    dtype = type_m.group(1).strip() if type_m else ""
                    if "llvmpipe" in gname.lower():
                        continue
                    dedup_key = f"{gid}_{gname.lower()}"
                    if dedup_key in seen_keys:
                        continue
                    seen_keys.add(dedup_key)
                    gpus.append({
                        "id": gid,
                        "backend_id": f"Vulkan{gid}",
                        "name": gname,
                        "vram_gb": _read_drm_vram_gb(gid, total_ram_gb, "INTEGRATED" in dtype),
                        "backend": "Vulkan"
                    })
        except:
            pass

    if not gpus:
        try:
            lspci_out = subprocess.check_output(["lspci"], text=True)
            idx = 0
            for line in lspci_out.splitlines():
                if any(k in line for k in ["VGA compatible controller", "Display controller", "3D controller"]):
                    desc = line.split(":", 2)[-1].strip()
                    dedup_key = f"{idx}_{desc.lower()}"
                    if dedup_key in seen_keys:
                        continue
                    seen_keys.add(dedup_key)
                    vram = _read_drm_vram_gb(idx, total_ram_gb, False)
                    gpus.append({
                        "id": idx,
                        "backend_id": f"Device{idx}",
                        "name": desc,
                        "vram_gb": vram,
                        "backend": "GPU"
                    })
                    idx += 1
        except:
            pass

    total_vram_gb = round(sum(g["vram_gb"] for g in gpus), 2)

    return {
        "cpu_name": cpu_name,
        "cpu_arch": cpu_arch,
        "cpu_flags": cpu_flags,
        "ram_gb": total_ram_gb,
        "total_vram_gb": total_vram_gb,
        "gpus": gpus
    }

def _read_drm_vram_gb(card_idx, fallback_ram, is_igpu):
    vram_file = f"/sys/class/drm/card{card_idx}/device/mem_info_vram_total"
    gtt_file = f"/sys/class/drm/card{card_idx}/device/mem_info_gtt_total"
    try:
        if os.path.exists(vram_file):
            with open(vram_file, "r") as f:
                vram_b = int(f.read().strip())
                if vram_b < 4 * (1024**3) and os.path.exists(gtt_file):
                    with open(gtt_file, "r") as gf:
                        gtt_b = int(gf.read().strip())
                        return round(gtt_b / (1024**3), 2)
                return round(vram_b / (1024**3), 2)
    except:
        pass
    return round(fallback_ram * 0.5, 2) if is_igpu else 0.0

def read_drm_vram_used_gb(card_idx):
    vram_used_file = f"/sys/class/drm/card{card_idx}/device/mem_info_vram_used"
    gtt_used_file = f"/sys/class/drm/card{card_idx}/device/mem_info_gtt_used"
    try:
        if os.path.exists(vram_used_file):
            with open(vram_used_file, "r") as f:
                used_b = int(f.read().strip())
                return round(used_b / (1024**3), 2)
        elif os.path.exists(gtt_used_file):
            with open(gtt_used_file, "r") as f:
                used_b = int(f.read().strip())
                return round(used_b / (1024**3), 2)
    except Exception:
        pass
    return 0.0


```

## Dosya: core/hf_downloader.py
```python
import os
import re
import requests
from PyQt6.QtCore import QThread, pyqtSignal

QUANT_PATTERNS = [
    "Q8_0", "Q6_K_L", "Q6_K", "Q5_K_L", "Q5_K_M", "Q5_K_S",
    "Q4_K_L", "Q4_K_M", "Q4_K_S", "Q4_0", "IQ4_XS", "IQ4_NL",
    "Q3_K_L", "Q3_K_M", "Q3_K_S", "IQ3_M", "IQ3_XS",
    "Q2_K_L", "Q2_K", "IQ2_M", "IQ2_XXS", "BF16", "F16", "F32"
]

def detect_capabilities_from_tags_and_name(model_id, tags=None):
    tags = [t.lower() for t in (tags or [])]
    name_low = model_id.lower()
    caps = {"thinking": False, "tools": False, "vision": False, "audio": False}
    if any(k in name_low for k in ["r1", "qwq", "qwen3", "thinking", "reasoning", "marco-o1", "sky-t1"]) or "reasoning" in tags:
        caps["thinking"] = True
    if any(k in name_low for k in ["coder", "instruct", "qwen", "llama-3", "mistral", "hermes", "function", "tool"]) or "conversational" in tags:
        caps["tools"] = True
    if any(k in name_low for k in ["-vl", "vision", "llava", "pixtral", "minicpm-v", "gemma-3", "qwen2.5-vl"]) or "image-text-to-text" in tags or "vision" in tags:
        caps["vision"] = True
    if any(k in name_low for k in ["audio", "omni", "whisper", "ultravox", "qwen2-audio"]) or "audio-text-to-text" in tags:
        caps["audio"] = True
    return caps

def extract_quant_from_filename(filename):
    up = filename.upper()
    for q in QUANT_PATTERNS:
        if q in up:
            return q
    m = re.search(r"([I]?Q\d_[A-Z0-9_]+|BF16|F16)", up)
    return m.group(1) if m else "GGUF"


class HFSearchWorker(QThread):
    results_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, query="", mode="trending", limit=25, token=""):
        super().__init__()
        self.query = query.strip()
        self.mode = mode
        self.limit = limit
        self.token = token.strip()

    def run(self):
        try:
            headers = {"User-Agent": "TrayAI/2.0"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            # SADECE DİL MODELLERİ (Text-Generation) Filtresi!
            # Flux, SD, embedding modelleri hariç tutulur.
            params = {
                "filter": "gguf",
                "pipeline_tag": "text-generation",
                "limit": self.limit,
                "full": "true"
            }

            if self.query:
                params["search"] = self.query
                params["sort"] = "downloads"
                params["direction"] = "-1"
            else:
                if self.mode == "trending":
                    params["sort"] = "trendingScore"
                elif self.mode == "likes":
                    params["sort"] = "likes"
                    params["direction"] = "-1"
                elif self.mode == "recent":
                    params["sort"] = "lastModified"
                    params["direction"] = "-1"
                else:
                    params["sort"] = "downloads"
                    params["direction"] = "-1"

            resp = requests.get("https://huggingface.co/api/models", params=params, headers=headers, timeout=12)
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data:
                mid = item.get("id", "")
                if not mid:
                    continue
                # Ek filtre: embedding ve diffusers modellerini temizle
                m_low = mid.lower()
                if any(x in m_low for x in ["bge-", "embed", "flux", "diffusion", "stable-diffusion"]):
                    continue

                tags = item.get("tags", [])
                caps = detect_capabilities_from_tags_and_name(mid, tags)
                results.append({
                    "id": mid,
                    "downloads": item.get("downloads", 0),
                    "likes": item.get("likes", 0),
                    "trending": item.get("trendingScore", 0),
                    "caps": caps
                })

            self.results_ready.emit(results)
        except Exception as e:
            self.error_occurred.emit(str(e))


class HFFilesWorker(QThread):
    files_ready = pyqtSignal(str, list)
    error_occurred = pyqtSignal(str)

    def __init__(self, repo_id, token=""):
        super().__init__()
        self.repo_id = repo_id
        self.token = token.strip()

    def run(self):
        try:
            headers = {"User-Agent": "TrayAI/2.0"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            url = f"https://huggingface.co/api/models/{self.repo_id}/tree/main"
            resp = requests.get(url, headers=headers, timeout=12)
            resp.raise_for_status()
            tree = resp.json()

            gguf_files = []
            for node in tree:
                path = node.get("path", "")
                if path.lower().endswith(".gguf"):
                    size_bytes = node.get("size", 0)
                    if "lfs" in node and isinstance(node["lfs"], dict):
                        size_bytes = node["lfs"].get("size", size_bytes)
                    size_gb = round(size_bytes / (1024 ** 3), 2) if size_bytes > 0 else 0.0
                    quant = extract_quant_from_filename(path)
                    dl_url = f"https://huggingface.co/{self.repo_id}/resolve/main/{path}"
                    gguf_files.append({
                        "filename": os.path.basename(path),
                        "rel_path": path,
                        "size_gb": size_gb,
                        "quant": quant,
                        "url": dl_url,
                        "repo_id": self.repo_id
                    })

            self.files_ready.emit(self.repo_id, gguf_files)
        except Exception as e:
            self.error_occurred.emit(str(e))


class DownloadWorker(QThread):
    progress = pyqtSignal(str, int, float, float, float)
    status_changed = pyqtSignal(str, str)
    finished_dl = pyqtSignal(str, str)
    error = pyqtSignal(str, str)

    def __init__(self, task_id, url, dest_path, token=""):
        super().__init__()
        self.task_id = task_id
        self.url = url
        self.dest_path = dest_path
        self.token = token.strip()
        self._is_paused = False
        self._is_cancelled = False

    def pause(self):
        self._is_paused = True
        self.status_changed.emit(self.task_id, "paused")

    def resume(self):
        self._is_paused = False
        self.status_changed.emit(self.task_id, "downloading")

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        import time
        try:
            self.status_changed.emit(self.task_id, "downloading")
            part_path = self.dest_path + ".part"
            downloaded_bytes = os.path.getsize(part_path) if os.path.exists(part_path) else 0

            headers = {"User-Agent": "TrayAI/2.0"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            if downloaded_bytes > 0:
                headers["Range"] = f"bytes={downloaded_bytes}-"

            response = requests.get(self.url, headers=headers, stream=True, timeout=20, allow_redirects=True)
            response.raise_for_status()

            total_size = downloaded_bytes
            content_length = response.headers.get("content-length")
            if content_length:
                total_size += int(content_length)

            mode = "ab" if downloaded_bytes > 0 else "wb"
            last_emit_time = time.time()
            bytes_since_last = 0

            with open(part_path, mode) as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if self._is_cancelled:
                        f.close()
                        if os.path.exists(part_path):
                            os.remove(part_path)
                        self.status_changed.emit(self.task_id, "cancelled")
                        return

                    while self._is_paused:
                        self.msleep(250)
                        if self._is_cancelled:
                            f.close()
                            if os.path.exists(part_path):
                                os.remove(part_path)
                            self.status_changed.emit(self.task_id, "cancelled")
                            return

                    if chunk:
                        f.write(chunk)
                        chunk_len = len(chunk)
                        downloaded_bytes += chunk_len
                        bytes_since_last += chunk_len

                        now = time.time()
                        elapsed = now - last_emit_time
                        if elapsed >= 0.3 or downloaded_bytes == total_size:
                            speed_mb = (bytes_since_last / (1024 * 1024)) / max(0.05, elapsed)
                            pct = int((downloaded_bytes / total_size) * 100) if total_size > 0 else 0
                            self.progress.emit(
                                self.task_id,
                                pct,
                                downloaded_bytes / (1024 * 1024),
                                total_size / (1024 * 1024),
                                speed_mb
                            )
                            last_emit_time = now
                            bytes_since_last = 0

            os.replace(part_path, self.dest_path)
            self.status_changed.emit(self.task_id, "completed")
            self.finished_dl.emit(self.task_id, self.dest_path)
        except Exception as e:
            self.error.emit(self.task_id, str(e))

```

## Dosya: core/__init__.py
```python

```

## Dosya: core/server_manager.py
```python
import ctypes
import subprocess
import os
import signal
import time
import requests
from PyQt6.QtCore import QThread, pyqtSignal


def _set_pdeathsig():
    # PR_SET_PDEATHSIG = 1, SIGKILL = 9 (Python çökerse alt süreç anında ölür)
    try:
        libc = ctypes.CDLL("libc.so.6")
        libc.prctl(1, 9)
    except Exception:
        pass

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
        total_prompt = s.get("n_prompt_tokens", 0)
        
        # Gerçek işlenen prompt token miktarı
        n_prompt_proc = s.get("n_prompt_tokens_processed", None)
        n_past = s.get("n_past", 0)
        if n_prompt_proc is None:
            n_prompt_proc = n_past

        tokens_list = s.get("tokens", [])
        tokens_len = len(tokens_list) if isinstance(tokens_list, list) else 0
        actual_ctx_used = max(n_past, tokens_len, total_prompt + n_decoded)

        timings = s.get("timings", {})
        pp_speed = timings.get("prompt_per_second", 0.0)
        tg_speed = timings.get("predicted_per_second", 0.0)

        grammar = str(s.get("grammar", "")) + str(s.get("params", {}).get("grammar", ""))
        has_tool_grammar = len(grammar.strip()) > 0 or "tool" in str(s).lower()

        info = {
            "is_processing": is_proc,
            "state": state,
            "n_ctx": n_ctx,
            "n_past": actual_ctx_used,
            "n_decoded": n_decoded,
            "n_prompt": total_prompt,
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

            # Prompt değerlendirme aşaması: Token üretimi başlamamış ve işlenen token hedef prompttan az
            if n_decoded == 0 and (total_prompt == 0 or n_prompt_proc < total_prompt):
                info["phase"] = "prompt"
                if total_prompt > 0:
                    pct = int((n_prompt_proc / total_prompt) * 100)
                    info["prompt_pct"] = max(1, min(99, pct))
                else:
                    simulated_pct = int(95 * (1.0 - (0.5 ** (elapsed / 2.5))))
                    info["prompt_pct"] = max(5, min(95, simulated_pct))
            else:
                info["phase"] = "eval"
                info["prompt_pct"] = 100
                if n_decoded > 0:
                    info["tokens_generated"] = n_decoded
                    if tg_speed <= 0:
                        info["tg_speed"] = round(n_decoded / elapsed, 1)
                else:
                    info["tokens_generated"] = actual_ctx_used
        else:
            self._was_generating = False
            info["phase"] = "idle"
            info["prompt_pct"] = 100
            info["tokens_generated"] = n_decoded if n_decoded > 0 else actual_ctx_used

        self.telemetry_update.emit(info)


class ServerManager:
    def __init__(self, engines_dir="engines"):
        self.engines_dir = os.path.abspath(engines_dir)
        self.process = None
        self.reader_thread = None

    def get_clean_system_env(self, extra_env=None):
        """
        PyInstaller'ın paketlediği eski libstdc++.so.6'nın sistemdeki
        güncel motoru bozmasını engeller.
        """
        run_env = os.environ.copy()

        # PyInstaller'ın enjekte ettiği LD_LIBRARY_PATH'i temizle
        orig_ld = run_env.get("LD_LIBRARY_PATH", "")
        cleaned_paths = []
        for p in orig_ld.split(":"):
            if p and "_internal" not in p and "/opt/tray-ai" not in p:
                cleaned_paths.append(p)

        # Önceliği her zaman motorun kendi klasörüne ve sistem kütüphanelerine ver
        system_lib_paths = [
            self.engines_dir,
            "/usr/lib/x86_64-linux-gnu",
            "/usr/lib",
            "/lib/x86_64-linux-gnu",
            "/lib"
        ]
        
        final_ld = ":".join(system_lib_paths + cleaned_paths)
        run_env["LD_LIBRARY_PATH"] = final_ld

        if extra_env:
            run_env.update(extra_env)
        return run_env

    def start_model(self, engine_name, model_path, host="127.0.0.1", port=8080, 
                    ngl=99, ctx=4096, extra_flags=None, env_vars=None, total_layers=32):
        if self.is_running():
            self.stop_model()

        engine_path = os.path.join(self.engines_dir, engine_name)
        if not os.path.exists(engine_path):
            fallback_paths = [
                os.path.join(os.path.expanduser("~/.local/share/tray-ai/engines"), engine_name),
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
                raise FileNotFoundError(f"Motor bulunamadı: {engine_path}")

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

        run_env = self.get_clean_system_env(env_vars)

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=self.engines_dir,
            env=run_env,
            start_new_session=True, preexec_fn=_set_pdeathsig)

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

```

## Dosya: core/whisper_manager.py
```python
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

```

## Dosya: generate_full_context.sh
```bash
#!/usr/bin/env bash
set -e

OUTPUT="CONTEXT.md"
TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
GIT_REV=$(git log -1 --format="%h (%ci)" 2>/dev/null || echo "Git bilgisi yok")

echo ">>> CONTEXT.md oluşturuluyor (Zaman: $TIMESTAMP)..."

cat << CONTEXT_HEADER > "$OUTPUT"
# TRAY-AI PROJE HAFIZA VE KAYNAK KOD DÖKÜMANI
- **Son Güncelleme:** $TIMESTAMP
- **Git Commit:** $GIT_REV

## 1. Geliştirici ve Donanım Profili
- **Geliştirici:** Baybora (Elektronik ve yazılım uzmanı).
- **İşletim Sistemi:** Linux Mint (Sadece saf Linux mimarisi).
- **Ana Donanım:** AMD Ryzen 7 8700G (Radeon 780M iGPU), 96GB DDR5 RAM, AMD Radeon RX 6600 dGPU.
- **İkinci Sistem:** AMD Ryzen 7 5700G, 64GB DDR4 RAM.
- **Odak / Hedef:** Yerel LLM'leri düşük maliyetle, yüksek verimle ve saf Linux üzerinde Vulkan hızlandırmasıyla çalıştırmak.

## 2. Proje Mimarisi ve Temel Kurallar
- **Adı:** Tray-AI
- **Arayüz:** PyQt6 (Sistem tepsisi odaklı, modern kart tasarımlı arayüz).
- **Çalışma Prensibi:** GGUF modellerini yönetir, bağımsız Vulkan/AVX2 destekli \`llama-server\` sürecini (PID) kontrol eder.
- **Dağıtım Biçimi:** All-in-one bağımsız paket (.deb ve .rpm). \`engines/llama-server\` ikilisini içine gömer, harici kütüphane bağımlılığı istemez.

---

## 3. PROJE DİZİN AĞACI
\`\`\`text
CONTEXT_HEADER

# Dizin yapısını çıkar (.git, build, dist, venv, cache hariç; .github DAHİL)
find . \
  -not -path "*/.git/*" -not -name ".git" \
  -not -path "*/build*" \
  -not -path "*/dist*" \
  -not -path "*/__pycache__*" \
  -not -path "*/package_root*" \
  -not -path "*/.venv*" \
  -not -path "*/venv*" \
  -not -path "*/.pytest_cache*" \
  | sort >> "$OUTPUT"

echo '```' >> "$OUTPUT"
echo "" >> "$OUTPUT"

echo "# 4. PROJE DOSYALARI VE KAYNAK KODLAR" >> "$OUTPUT"

# İkili (binary) olmayan tüm kaynak dosyalarını tara
# .github altındakiler dahil, sadece .git ve geçici derleme klasörleri hariç
find . -type f \
  \( -name "*.py" -o -name "*.json" -o -name "*.yml" -o -name "*.yaml" -o -name "*.sh" -o -name "*.qss" -o -name "*.txt" -o -name "*.desktop" -o -name ".gitignore" \) \
  -not -path "*/.git/*" \
  -not -path "*/build*" \
  -not -path "*/dist*" \
  -not -path "*/__pycache__*" \
  -not -path "*/package_root*" \
  -not -path "*/.venv*" \
  -not -path "*/venv*" \
  -not -path "*/.pytest_cache*" \
  -not -name "CONTEXT.md" \
  | sort | while read -r filepath; do
    
    clean_path="${filepath#./}"
    filename=$(basename "$clean_path")
    ext="${clean_path##*.}"
    
    case "$ext" in
      py) lang_syntax="python" ;;
      json) lang_syntax="json" ;;
      yml|yaml) lang_syntax="yaml" ;;
      sh) lang_syntax="bash" ;;
      qss) lang_syntax="css" ;;
      txt|desktop) lang_syntax="text" ;;
      *)
        if [ "$filename" = ".gitignore" ]; then
          lang_syntax="gitignore"
        else
          lang_syntax="text"
        fi
        ;;
    esac

    echo "" >> "$OUTPUT"
    echo "## Dosya: $clean_path" >> "$OUTPUT"
    echo "\`\`\`$lang_syntax" >> "$OUTPUT"
    cat "$filepath" >> "$OUTPUT"
    echo "" >> "$OUTPUT"
    echo "\`\`\`" >> "$OUTPUT"
done

echo ""
echo "✅ CONTEXT.md başarıyla güncellendi! ($TIMESTAMP)"
echo "   - .github altındaki tüm iş akışları dahil edildi."
echo "   - .git ve geçici derleme klasörleri elendi."

```

## Dosya: .github/workflows/package.yml
```yaml
name: Tray-AI Otomatik Linux Paketleyici

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

permissions:
  contents: write

jobs:
  build-linux:
    runs-on: ubuntu-22.04

    steps:
    - name: 1. Kodlari Cek
      uses: actions/checkout@v4

    - name: 2. Python Kur
      uses: actions/setup-python@v5
      with:
        python-version: '3.10'

    - name: 3. Vulkan SDK ve Paketleme Araclari
      run: |
        sudo apt-get update
        sudo apt-get install -y wget gnupg ca-certificates ruby ruby-dev rubygems build-essential rpm cmake git pkg-config libcurl4-openssl-dev

        wget -qO - https://packages.lunarg.com/lunarg-signing-key-pub.asc | sudo gpg --dearmor -o /usr/share/keyrings/lunarg-archive-keyring.gpg
        echo "deb [signed-by=/usr/share/keyrings/lunarg-archive-keyring.gpg] https://packages.lunarg.com/vulkan jammy main" | sudo tee /etc/apt/sources.list.d/lunarg-vulkan-jammy.list

        sudo apt-get update
        sudo apt-get install -y vulkan-sdk

        sudo gem install --no-document fpm
        python -m pip install --upgrade pip
        pip install pyinstaller
        if [ -f requirements.txt ]; then pip install -r requirements.txt; fi

    - name: 4. llama-server Derle (Vulkan ve AVX2)
      run: |
        rm -rf /tmp/llama-build
        git clone --depth 1 https://github.com/ggml-org/llama.cpp.git /tmp/llama-build
        cd /tmp/llama-build
        
        cmake -B build \
          -DBUILD_SHARED_LIBS=OFF \
          -DGGML_NATIVE=OFF \
          -DGGML_AVX2=ON \
          -DGGML_VULKAN=ON
          
        cmake --build build --config Release --target llama-server -j$(nproc)
        
        cd ${{ github.workspace }}
        mkdir -p engines
        cp -f /tmp/llama-build/build/bin/llama-server engines/llama-server
        chmod +x engines/*
        rm -rf /tmp/llama-build

    - name: 5. PyInstaller ile Paketle
      run: |
        pyinstaller --noconfirm --onedir --windowed \
          --name "tray-ai" \
          --add-data "assets:assets" \
          --add-data "core:core" \
          --add-data "ui:ui" \
          --add-data "lang:lang" \
          --add-data "engines:engines" \
          main.py

        # PyInstaller'ın içine kopyaladığı eski libstdc++ dosyasını kaldırıyoruz ki sistemin kendi güncel kütüphanesini kullansın
        find dist/tray-ai -name "libstdc++.so*" -delete || true
        find dist/tray-ai -name "libgcc_s.so*" -delete || true

    - name: 6. Deb ve Rpm Paketlerini Olustur
      env:
        REF_NAME: ${{ github.ref_name }}
      run: |
        mkdir -p package_root/opt/tray-ai
        mkdir -p package_root/usr/bin
        mkdir -p package_root/usr/share/applications
        mkdir -p package_root/usr/share/icons/hicolor/scalable/apps
        cp -r dist/tray-ai/* package_root/opt/tray-ai/
        ln -s /opt/tray-ai/tray-ai package_root/usr/bin/tray-ai
        if [ -f assets/tray-ai.svg ]; then
          cp assets/tray-ai.svg package_root/usr/share/icons/hicolor/scalable/apps/tray-ai.svg
        fi
        printf "[Desktop Entry]\nVersion=1.0\nType=Application\nName=Tray AI Server\nComment=Local GGUF LLM Server\nExec=/usr/bin/tray-ai\nIcon=tray-ai\nTerminal=false\nCategories=Development;Utility;\n" > package_root/usr/share/applications/tray-ai.desktop

        # Tag adını kesin olarak kırp
        RAW_TAG="${REF_NAME}"
        CLEAN_VER="${RAW_TAG#v}"

        if [ -z "$CLEAN_VER" ] || [ "$CLEAN_VER" = "main" ]; then
          PKG_VERSION="1.0.0"
        else
          PKG_VERSION="$CLEAN_VER"
        fi

        echo ">>> PAKETLENECEK KESİN SÜRÜM: $PKG_VERSION <<<"

        fpm -s dir -t deb -n tray-ai -v "$PKG_VERSION" \
          --description "Tray AI: Local GGUF LLM Server in System Tray" \
          --depends libxcb-cursor0 --depends libvulkan1 \
          -C package_root -p "tray-ai_${PKG_VERSION}_amd64.deb" .

        fpm -s dir -t rpm -n tray-ai -v "$PKG_VERSION" \
          --description "Tray AI: Local GGUF LLM Server in System Tray" \
          --depends xcb-util-cursor --depends vulkan-loader \
          -C package_root -p "tray-ai-${PKG_VERSION}.x86_64.rpm" .

    - name: 7. Paketleri Actions Yapisi Olarak Sakla (Artifact)
      uses: actions/upload-artifact@v4
      with:
        name: linux-packages
        path: |
          *.deb
          *.rpm

    - name: 8. Paketleri Release'e Yukle
      uses: softprops/action-gh-release@v2
      if: startsWith(github.ref, 'refs/tags/')
      with:
        files: |
          *.deb
          *.rpm
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

```

## Dosya: .gitignore
```gitignore
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
#  Usually these files are written by a python script from a template
#  before PyInstaller builds the exe, so as to inject date/other infos into it.
*.manifest
*.spec

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/
cover/

# Translations
*.mo
*.pot

# Django stuff:
*.log
local_settings.py
db.sqlite3
db.sqlite3-journal

# Flask stuff:
instance/
.webassets-cache

# Scrapy stuff:
.scrapy

# Sphinx documentation
docs/_build/

# PyBuilder
.pybuilder/
target/

# Jupyter Notebook
.ipynb_checkpoints

# IPython
profile_default/
ipython_config.py

# pyenv
#   For a library or package, you might want to ignore these files since the code is
#   intended to run in multiple environments; otherwise, check them in:
# .python-version

# pipenv
#   According to pypa/pipenv#598, it is recommended to include Pipfile.lock in version control.
#   However, in case of collaboration, if having platform-specific dependencies or dependencies
#   having no cross-platform support, pipenv may install dependencies that don't work, or not
#   install all needed dependencies.
#Pipfile.lock

# UV
#   Similar to Pipfile.lock, it is generally recommended to include uv.lock in version control.
#   This is especially recommended for binary packages to ensure reproducibility, and is more
#   commonly ignored for libraries.
#uv.lock

# poetry
#   Similar to Pipfile.lock, it is generally recommended to include poetry.lock in version control.
#   This is especially recommended for binary packages to ensure reproducibility, and is more
#   commonly ignored for libraries.
#   https://python-poetry.org/docs/basic-usage/#commit-your-poetrylock-file-to-version-control
#poetry.lock

# pdm
#   Similar to Pipfile.lock, it is generally recommended to include pdm.lock in version control.
#pdm.lock
#   pdm stores project-wide configurations in .pdm.toml, but it is recommended to not include it
#   in version control.
#   https://pdm.fming.dev/latest/usage/project/#working-with-version-control
.pdm.toml
.pdm-python
.pdm-build/

# PEP 582; used by e.g. github.com/David-OConnor/pyflow and github.com/pdm-project/pdm
__pypackages__/

# Celery stuff
celerybeat-schedule
celerybeat.pid

# SageMath parsed files
*.sage.py

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Spyder project settings
.spyderproject
.spyproject

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# Pyre type checker
.pyre/

# pytype static type analyzer
.pytype/

# Cython debug symbols
cython_debug/

# PyCharm
#  JetBrains specific template is maintained in a separate JetBrains.gitignore that can
#  be found at https://github.com/github/gitignore/blob/main/Global/JetBrains.gitignore
#  and can be added to the global gitignore or merged into this file.  For a more nuclear
#  option (not recommended) you can uncomment the following to ignore the entire idea folder.
#.idea/

# Ruff stuff:
.ruff_cache/

# PyPI configuration file
.pypirc

# Cursor  
#  Cursor is an AI-powered code editor.`.cursorignore` specifies files/directories to 
#  exclude from AI features like autocomplete and code analysis. Recommended for sensitive data
#  refer to https://docs.cursor.com/context/ignore-files
.cursorignore
.cursorindexingignore
```

## Dosya: lang/en.json
```json
{
  "drag_hint": "(Drag here to move)",
  "srv_wait_model": "● Server Active (Waiting for Model)",
  "srv_loading": "● Loading Model...",
  "srv_ready": "● Model Loaded && Ready",
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
  "btn_show_folder": "📁 Show in Files",
  "btn_delete": "🗑️ Delete",
  "search_model_placeholder": "🔎 Search local models (name, arch, quant)...",
  "filter_all": "All Models",
  "filter_mtp": "⚡ MTP Supported",
  "filter_yarn": "🧶 YaRN Supported",
  "filter_thinking": "🧠 Reasoning Models",
  "filter_tools": "🔧 Tool / Agent Calling",
  "filter_moe": "🧩 MoE Models",
  "filter_vision": "👁️ Vision (VLM)",
  "sort_name": "By Name (A-Z)",
  "sort_size_asc": "By Size (Smallest First)",
  "sort_size_desc": "By Size (Largest First)",
  "sort_ctx": "By Context (Max Ctx)",
  "lbl_models_summary": "📦 <b>Shown: {shown} / {total} Models</b> • Total Disk: <b>{size} GB</b> (Double-click to load)",
  "lbl_no_folder": "Not Selected",
  "lbl_no_meta": "No Model Selected — Waiting for metadata...",
  "btn_inspect": "🔍 GGUF Metadata && Template Inspector",
  "btn_autotune": "⚡ Auto-Tune for System Hardware",
  "grp_ctx": "1. Context Length && GPU Offload",
  "lbl_ctx": "Context Length (-c):",
  "lbl_ngl": "GPU Offload Layers (-ngl):",
  "grp_kv": "2. K Cache / V Cache Quantization && Memory",
  "chk_kv_gpu": "Offload KV Cache to GPU",
  "chk_mmap": "Use mmap()",
  "chk_prompt_cache": "⚡ Prompt Caching (Instant Coding / Snapshot)",
  "chk_mlock": "Use mlock() (Keep in RAM)",
  "grp_batch": "3. CPU Threads, Batch Size && RoPE Settings",
  "lbl_parallel": "Parallel Request Slots (-np):",
  "grp_spec": "4. Reasoning Effort && Speculative Decoding (MTP / Draft)",
  "lbl_effort": "Reasoning Effort:",
  "eff_items": [
    "Disabled",
    "Low",
    "Medium",
    "High",
    "Custom Budget"
  ],
  "lbl_custom_budget": "Custom Budget:",
  "chk_mtp_supported": "⚡ MTP ({layers} Layer Speculative Decoding) Active — [{reason}]",
  "chk_mtp_none": "MTP Not Detected in Model (Click to Force Enable)",
  "chk_draft": "Draft Model:",
  "btn_pick_draft": "Select Model...",
  "grp_samp": "5. Samplers (Temperature, Top-K/P, Min-P, Penalties, Seed)",
  "lbl_temp": "Temperature (Temp):",
  "lbl_seed": "Seed:",
  "grp_adv_samp": "6. Advanced Samplers (DRY, XTC, Dynamic Temp, YaRN && MoE)",
  "grp_cli": "7. Chat Template Override && Extra CLI Flags",
  "lbl_chat_template": "Chat Template Scheme:",
  "template_auto": "Auto (Embedded Model Jinja Template)",
  "lbl_custom_flags": "Extra Custom Arguments:",
  "custom_flags_placeholder": "e.g. --override-kv llama.expert_used_count=int:4 --no-context-shift",
  "hw_cpu_ok": "<b>Processor (CPU)</b> <span style='color:#9ece6a;'>✓ Compatible</span>",
  "hw_isa": "Instruction Sets:",
  "hw_sys_ram": "<b>System RAM:</b>",
  "hw_tot_vram": "<b>Total VRAM:</b>",
  "hw_gpus": "Detected GPU Hardware",
  "hw_split": "Multi-GPU Split Strategy:",
  "hw_split_items": [
    "Split Evenly / Layer Split",
    "Row Split",
    "Single GPU (First Active Device Only)"
  ],
  "hw_mon": "Live Resource Monitor",
  "srv_mgmt": "Server Service Management",
  "srv_state_on": "🟢 <b>Server Service: ACTIVE</b>",
  "srv_state_off": "🔴 <b>Server Service: STOPPED</b>",
  "btn_srv_stop": "Stop Server",
  "btn_srv_start": "Start Server",
  "srv_net_grp": "Network, IP, Port && Agent (MCP/Tool) Configuration",
  "lbl_port": "Server Port:",
  "btn_copy_api": "📋 Copy API URL",
  "chk_lan": "Expose on Local Network (0.0.0.0 - Allow LAN clients)",
  "chk_cors": "Enable CORS Headers (* - Built-in Active)",
  "chk_tools": "Enable Remote Client Tool && Agent Calls (Jinja / Tool Calling / MCP)",
  "srv_logs": "Live llama-server Output && Loading Logs",
  "hf_placeholder": "Search GGUF Models (e.g. Qwen3, DeepSeek-R1, Llama-3.3, Gemma-3)...",
  "btn_search": "🔍 Search",
  "btn_hf_trend": "🔥 Trending",
  "btn_hf_dl": "⬇️ Most Downloaded",
  "btn_hf_likes": "⭐ Most Liked",
  "btn_hf_new": "🆕 Recently Updated",
  "hf_models_lbl": "Hugging Face GGUF Models (Click a model to list quant files):",
  "hf_files_lbl": "Available Quant (.gguf) Files in Repository:",
  "dl_active_grp": "Download Queue && Status",
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
  "grp_runtime": "⚡ Runtime && Engines (llama.cpp Engine Management && Updates)",
  "chk_auto_update_eng": "Auto-update Runtime Engines (Check updates on startup)",
  "btn_check_eng_updates": "🔄 Check for Updates",
  "set_grp_lang": "Language && Appearance",
  "lbl_ui_lang": "Interface Language:",
  "lang_auto": "Automatic by System Locale (Auto)",
  "set_grp_sys": "System Integration && Startup",
  "chk_autostart": "Automatically start Tray AI in system tray on login",
  "btn_install_desktop": "🖥️ Re-register Application Menu Icon (.desktop)",
  "set_grp_hf": "Hugging Face API Settings",
  "lbl_hf_token": "HF Access Token (Optional, for gated models && higher rate limits):",
  "tray_toggle": "Show / Hide Window",
  "tray_settings": "⚙️ Settings",
  "tray_exit": "Quit Application",
  "pwd_title": "System Password Required (sudo)",
  "pwd_prompt": "To completely flush system RAM cache, please enter your sudo password:",
  "ram_freed_title": "RAM Cache Cleared",
  "ram_freed_msg": "✅ System RAM cache successfully flushed!\nPrevious: {before} GB\nCurrent: {after} GB\nNet Memory Freed: {diff} GB",
  "ram_err_msg": "❌ Incorrect password or permission denied!",
  "speed_prefix": "⚡ Speed: {val} t/s",
  "speed_pp": "⚡ PP: {val} t/s",
  "speed_tg": "⚡ TG: {val} t/s",
  "prompt_read_prefix": "📖 Prompt Read: %{val}",
  "tokens_prefix": "🔢 Tokens: {val}",
  "ctx_prefix": "📦 Ctx: {past} / {ctx}",
  "mem_est_initial": "💾 <b>Estimated Memory Usage:</b> Calculated when model is selected...",
  "mem_est_format": "💾 <b>Estimated Memory: {total} GB</b> (Model: {model} GB + KV Cache: {kv} GB) — <b>{status} (System: %{pct})</b>",
  "status_fits": "✅ Fits Comfortably",
  "status_borderline": "⚠️ Near Limit",
  "status_insufficient": "❌ May Run Out of Memory",
  "meta_summary_format": "<b>Model:</b> {fn} | <b>Arch:</b> {arch} | <b>Layers:</b> {layers} | <b>Ctx:</b> {ctx}<br><b>Features:</b> {mtp} | {yarn} | <b>Recommended ({src}):</b> <span style='color:#e0af68;'>Temp: {temp:.2f} • Top-P: {topp:.2f} • Min-P: {minp:.2f}</span>",
  "badge_mtp_active": "<span style='color:#9ece6a;'>✓ MTP ({layers}L)</span>",
  "badge_mtp_none": "<span style='color:#565f89;'>No MTP</span>",
  "badge_yarn_active": "<span style='color:#73daca;'>✓ YaRN</span>",
  "badge_yarn_none": "Standard RoPE",
  "models_summary_format": "📦 <b>Shown: {shown} / {total} Models</b> • Total Disk: <b>{size} GB</b> (Double-click to load)"
}
```

## Dosya: lang/tr.json
```json
{
  "drag_hint": "(Taşımak için sürükleyin)",
  "srv_wait_model": "● Sunucu Açık (Model Bekleniyor)",
  "srv_loading": "● Model Yükleniyor...",
  "srv_ready": "● Model Yüklü && Hazır",
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
  "btn_show_folder": "📁 Klasörde Göster",
  "btn_delete": "🗑️ Sil",
  "search_model_placeholder": "🔎 Yerel modellerde ara (isim, mimari, quant)...",
  "filter_all": "Tüm Modeller",
  "filter_mtp": "⚡ MTP Destekliler",
  "filter_yarn": "🧶 YaRN Destekliler",
  "filter_thinking": "🧠 Düşünen (Reasoning)",
  "filter_tools": "🔧 Araç / Ajan (Tools)",
  "filter_moe": "🧩 MoE Modeller",
  "filter_vision": "👁️ Görsel (Vision)",
  "sort_name": "İsme Göre (A-Z)",
  "sort_size_asc": "Boyuta Göre (Küçükten Büyüğe)",
  "sort_size_desc": "Boyuta Göre (Büyükten Küçüğe)",
  "sort_ctx": "Bağlama Göre (Max Ctx)",
  "lbl_models_summary": "📦 <b>Gösterilen: {shown} / {total} Model</b> • Toplam Disk: <b>{size} GB</b> (Çift tıklayarak yükleyin)",
  "lbl_no_folder": "Seçilmedi",
  "lbl_no_meta": "Model Seçilmedi — Metadata bekleniyor...",
  "btn_inspect": "🔍 GGUF Metadata && Şablon Müfettişi",
  "btn_autotune": "⚡ Donanıma Göre Otomatik Ayarla (Auto-Tune)",
  "grp_ctx": "1. Bağlam (Context) && GPU Yük Aktarma",
  "lbl_ctx": "Bağlam Uzunluğu (-c):",
  "lbl_ngl": "GPU Yük Aktarma Katmanı (-ngl):",
  "grp_kv": "2. K Cache / V Cache Nicemleme && Bellek Optimizasyonu",
  "chk_kv_gpu": "KV Cache GPU'da Tut",
  "chk_mmap": "mmap() Kullan",
  "chk_prompt_cache": "⚡ Prompt Caching (Anlık Kodlama / Snapshot)",
  "chk_mlock": "mlock() Bellekte Kilitle",
  "grp_batch": "3. CPU Çekirdek, Parti (Batch) && RoPE Frekans Ayarları",
  "lbl_parallel": "Paralel İstek Slotu (-np):",
  "grp_spec": "4. Düşünce Eforu (Reasoning) && Spekülatif Çözme (MTP / Draft)",
  "lbl_effort": "Düşünce Eforu:",
  "eff_items": [
    "Kapalı",
    "Düşük (Low)",
    "Orta (Medium)",
    "Yüksek (High)",
    "Özel Bütçe"
  ],
  "lbl_custom_budget": "Özel Bütçe:",
  "chk_mtp_supported": "⚡ MTP ({layers} Katman Spekülatif Tahmin) Aktif — [{reason}]",
  "chk_mtp_none": "Modelde MTP Desteği Yok (İsterseniz Zorla Açabilirsiniz)",
  "chk_draft": "Draft Model:",
  "btn_pick_draft": "Model Seç...",
  "grp_samp": "5. Örnekleyiciler (Temperature, Top-K/P, Min-P, Cezalar, Seed)",
  "lbl_temp": "Sıcaklık (Temp):",
  "lbl_seed": "Seed (Tohum):",
  "grp_adv_samp": "6. Gelişmiş Samplers (DRY, XTC, Dynamic Temp, YaRN && MoE)",
  "grp_cli": "7. Chat Template Override && Ekstra CLI Parametreleri",
  "lbl_chat_template": "Chat Template Şablonu:",
  "template_auto": "Otomatik (Modelin Gömülü Jinja Şablonu)",
  "lbl_custom_flags": "Ekstra Özel Argümanlar:",
  "custom_flags_placeholder": "Örn: --override-kv llama.expert_used_count=int:4 --no-context-shift",
  "hw_cpu_ok": "<b>İşlemci (CPU)</b> <span style='color:#9ece6a;'>✓ Uyumlu</span>",
  "hw_isa": "Komut Setleri:",
  "hw_sys_ram": "<b>Sistem RAM:</b>",
  "hw_tot_vram": "<b>Toplam VRAM:</b>",
  "hw_gpus": "Algılanan GPU Donanımları",
  "hw_split": "Çoklu GPU Dağıtım Stratejisi:",
  "hw_split_items": [
    "Eşit / Katman Bölme (Layer Split)",
    "Satır Bölme (Row Split)",
    "Tek GPU (Yalnızca İlk Aktif Kart)"
  ],
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
  "chk_tools": "Uzak İstemci Araç && Ajan Çağrıları (Jinja / Tool Calling / MCP) Aktif",
  "srv_logs": "Canlı llama-server Çıktısı && Yükleme Logları",
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
  "grp_runtime": "⚡ Runtime && Engines (llama.cpp Motor Yönetimi ve Güncelleme)",
  "chk_auto_update_eng": "Auto-update Runtime Engines (Başlangıçta güncellemeleri denetle)",
  "btn_check_eng_updates": "🔄 Güncellemeleri Denetle",
  "set_grp_lang": "Dil ve Görünüm (Language && Appearance)",
  "lbl_ui_lang": "Arayüz Dili:",
  "lang_auto": "Sistem Diline Göre Otomatik (Auto)",
  "set_grp_sys": "Sistem Entegrasyonu && Başlangıç",
  "chk_autostart": "Bilgisayar açıldığında Tray AI'ı sistem tepsisinde otomatik başlat",
  "btn_install_desktop": "🖥️ Uygulama Menüsüne Simgeyi Yeniden Kaydet (.desktop)",
  "set_grp_hf": "Hugging Face API Ayarları",
  "lbl_hf_token": "HF Erişim Tokenı (Gated modeller ve yüksek hız için isteğe bağlı):",
  "tray_toggle": "Pencereyi Göster / Gizle",
  "tray_settings": "⚙️ Ayarlar",
  "tray_exit": "Uygulamadan Çık",
  "pwd_title": "Sistem Parolası Gerekli (sudo)",
  "pwd_prompt": "Sistem RAM önbelleğini tamamen boşaltmak için sudo parolanızı girin:",
  "ram_freed_title": "RAM Önbelleği Temizlendi",
  "ram_freed_msg": "✅ Sistem RAM önbelleği başarıyla boşaltıldı!\nÖnceki: {before} GB\nŞimdiki: {after} GB\nKazanılan Net Bellek: {diff} GB",
  "ram_err_msg": "❌ Parola hatalı veya yetki verilemedi!",
  "speed_prefix": "⚡ Hız: {val} t/s",
  "speed_pp": "⚡ PP: {val} t/s",
  "speed_tg": "⚡ TG: {val} t/s",
  "prompt_read_prefix": "📖 Prompt Okuma: %{val}",
  "tokens_prefix": "🔢 Token: {val}",
  "ctx_prefix": "📦 Ctx: {past} / {ctx}",
  "mem_est_initial": "💾 <b>Tahmini Bellek Tüketimi:</b> Model seçildiğinde hesaplanır...",
  "mem_est_format": "💾 <b>Tahmini Bellek: {total} GB</b> (Model: {model} GB + KV Cache: {kv} GB) — <b>{status} (Sistem: %{pct})</b>",
  "status_fits": "✅ Rahat Sığar",
  "status_borderline": "⚠️ Sınırda",
  "status_insufficient": "❌ Bellek Yetersiz Olabilir",
  "meta_summary_format": "<b>Model:</b> {fn} | <b>Mimari:</b> {arch} | <b>Katman:</b> {layers} | <b>Ctx:</b> {ctx}<br><b>Özellikler:</b> {mtp} | {yarn} | <b>Önerilen ({src}):</b> <span style='color:#e0af68;'>Temp: {temp:.2f} • Top-P: {topp:.2f} • Min-P: {minp:.2f}</span>",
  "badge_mtp_active": "<span style='color:#9ece6a;'>✓ MTP ({layers}L)</span>",
  "badge_mtp_none": "<span style='color:#565f89;'>MTP Yok</span>",
  "badge_yarn_active": "<span style='color:#73daca;'>✓ YaRN</span>",
  "badge_yarn_none": "Standart RoPE",
  "models_summary_format": "📦 <b>Gösterilen: {shown} / {total} Model</b> • Toplam Disk: <b>{size} GB</b> (Çift tıklayarak yükleyin)"
}
```

## Dosya: main.py
```python
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
                "total_gb": max(0.5, g["vram_gb"])
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
                live_used = read_drm_vram_used_gb(gid)
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
        self.lbl_load_stage.setText("⏳ RAM / VRAM...")
        self.set_status_badge("loading", self.t("srv_loading"))
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
            self.btn_drop_cache.setEnabled(True)
            QMessageBox.critical(self, "Error", str(e))

    def unload_current_model(self):
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
        if pct > self.load_progress_bar.value():
            self.load_progress_bar.setValue(pct)
            self.lbl_load_stage.setText(f"⏳ {stage_text} (%{pct})")

    def on_health_loading_tick(self):
        target_gb = self.active_model_info.get("size_gb", 0.0) if self.active_model_info else 0.0
        proc = getattr(self.server_mgr, "process", None)
        
        if proc and proc.poll() is None and target_gb > 0:
            try:
                p = psutil.Process(proc.pid)
                # RSS (fiziksel RAM) ve VMS tüketimi
                rss_gb = p.memory_info().rss / (1024 ** 3)
                
                # Model ağırlıklarının aktarılma yüzdesi (küsuratlı)
                pct_float = min(99.0, (rss_gb / target_gb) * 100.0)
                int_pct = int(pct_float)
                
                if int_pct > self.load_progress_bar.value():
                    self.load_progress_bar.setValue(int_pct)
                
                self.lbl_load_stage.setText(
                    f"⏳ RAM/VRAM: {rss_gb:.2f} / {target_gb:.2f} GB (%{pct_float:.2f})"
                )
                return
            except Exception:
                pass

        # Geriye dönük yedek mantık
        cur = self.load_progress_bar.value()
        if cur < 95:
            self.load_progress_bar.setValue(cur + 1)
            self.lbl_load_stage.setText(f"⏳ RAM/VRAM Offloading... (%{cur + 1})")

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

```

## Dosya: requirements.txt
```text
PyQt6>=6.5.0
gguf>=0.10.0
huggingface_hub>=0.23.0
requests>=2.31.0
psutil>=5.9.0
numpy>=1.24.0

```

## Dosya: run.sh
```bash
#!/usr/bin/env bash
cd "$(dirname "$0")"
./venv/bin/python3 main.py

```

## Dosya: run_step3_git_and_context.sh
```bash
#!/usr/bin/env bash
set -e

echo "1. update_context.sh güncelleniyor..."
cat << 'CONTEXT_EOF' > update_context.sh
#!/usr/bin/env bash
cat << 'INNER_EOF' > CONTEXT.md
# TRAY-AI PROJE HAFIZA VE DURUM DÖKÜMANI

## 1. Proje Amacı ve Vizyonu
Linux Mint (ve diğer dağıtımlar) için PyQt6 tabanlı, sistem tepsisinde (system tray) sessizce çalışan, OpenAI ve Ollama API uyumlu hibrit yerel LLM/VLM sunucu yönetim aracı.
- Kullanıcı tek tıkla GGUF modellerini yönetir, bağlam, katman, örnekleyici ve donanım ayarlarını yapar.
- Bağımsız Vulkan/AVX2 destekli `llama-server` sürecini (PID) kontrol eder; ebeveyn ölüm sinyaliyle (PDEATHSIG) zombi süreçleri engeller.
- Dahili STT (Whisper Bas-Konuş) ve Vision (Görsel Analiz) desteği sunar.
- Paketler (.deb ve .rpm) **all-in-one** yapıdadır; kullanıcının harici bağımlılık kurmasına gerek kalmadan motorları içinde barındırır.

## 2. Donanım ve Çalışma Ortamı
- **Geliştirici:** Baybora
- **Ana Sistem:** AMD Ryzen 7 8700G (Radeon 780M iGPU), 96GB DDR5 RAM, AMD Radeon RX 6600 dGPU.
- **İkinci Sistem:** AMD Ryzen 7 5700G, 64GB DDR4 RAM.
- **İşletim Sistemi:** Linux Mint (Saf Linux mimarisi).
- **Hedef:** Düşük maliyetle/mevcut donanımla büyük modelleri (Qwen, DeepSeek vb.) Vulkan hızlandırmasıyla yerelde verimli çalıştırmak.

## 3. Mimari Bileşenler
- `main.py`: PyQt6 sistem tepsisi, tek parça alt konsol (Unified Bottom Dock), model ayar hafızası (persistence), tekerlek koruması (NoWheelEventFilter) ve masaüstü bildirimleri.
- `ui/chat_dialog.py`: Dahili Mini Playground. Canlı düşünce zinciri (Reasoning/Thinking) gösterimi, sürükle-bırak görsel analizi (Vision / VLM) ve anlık TTFT/Hız sayaçları.
- `ui/styles.py`: Koyu tema, sol kenar vurgulu kart panelleri (accent border) ve 6px minimal kaydırma çubukları.
- `core/hardware.py`: Linux `sysfs/drm` bellek arayüzünden kart bazlı anlık VRAM okuma (`read_drm_vram_used_gb`) ve CPU/RAM telemetry.
- `core/api_gateway.py`: OpenAI ve Ollama uyumlu çift protokol HTTP gateway. `BrokenPipeError` ve soket kopmalarına karşı korumalı akış mimarisi.
- `core/server_manager.py`: `llama-server` yönetimi, açılışta zombi süreç temizliği ve Linux `PR_SET_PDEATHSIG` çekirdek takibi.
- `core/gguf_parser.py`: GGUF metadata ayrıştırma, MTP (Multi-Token Prediction) ve YaRN uzun bağlam tespiti.
- `core/hf_downloader.py`: Hugging Face üzerinden sadece LLM/VLM modellerini süzme, arama ve parçalı indirme motoru.
- `core/whisper_manager.py`: ALSA `arecord` ve `whisper-cli` tabanlı yerel bas-konuş sesli asistan motoru.

## 4. Son Eklenen Yetenekler (v1.2 Sprint)
1. **Model Ayar Hafızası:** Modellerin katman, context, sıcaklık, batch ve sampler ayarlarının `config.json` içinde kalıcı saklanması.
2. **No-Wheel Event Koruması:** Sayfa kaydırılırken kutucuk değerlerinin istemsiz değişmesinin engellenmesi.
3. **Canlı Kart Bazlı VRAM Barları:** RX 6600 ve Radeon 780M kartlarının bellek doluluklarının anlık izlenmesi.
4. **Mini Playground (Chat & Vision):** Model düşünce zincirini gösteren ve görsel analizi destekleyen entegre test sohbeti.
5. **Modern Alt Konsol & Çerçevesiz Butonlar:** Telemetri ve model eylem butonlarının tek parça estetik konsolda toplanması.
6. **Masaüstü Bildirimleri:** Model yüklenmesi, indirme tamamlama ve sunucu durumlarının masaüstü balonlarıyla bildirilmesi.
INNER_EOF
chmod +x update_context.sh
echo "✅ update_context.sh güncellendi!"
CONTEXT_EOF

chmod +x update_context.sh
./update_context.sh

echo "2. generate_full_context.sh çalıştırılıyor (Tam kaynak kod dökümü)..."
if [ -f "./generate_full_context.sh" ]; then
    ./generate_full_context.sh
fi

echo "3. Git durumu kontrol ediliyor ve commit oluşturuluyor..."
git status -s

git add .
git commit -m "feat(ui, core): modernize arayuz, mini playground (vision+reasoning), canli vram barlari ve stabilizasyon" || echo "Commitlenecek yeni değişiklik bulunamadı."

echo ""
echo "✅ 3. Adım başarıyla tamamlandı! Kod tabanı ve CONTEXT.md tamamen senkronize."

```

## Dosya: ui/chat_dialog.py
```python
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

```

## Dosya: ui/__init__.py
```python

```

## Dosya: ui/styles.py
```python
DARK_STYLE = """
QWidget {
    background-color: #1a1b26;
    color: #c0caf5;
    font-family: 'Ubuntu', 'Segoe UI', sans-serif;
    font-size: 13px;
}
QToolTip {
    background-color: #1f2335;
    color: #c0caf5;
    border: 1px solid #3b4261;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 11px;
}
QTabWidget::pane {
    border: 1px solid #24283b;
    background: #16161e;
    border-radius: 8px;
}
QTabBar::tab {
    background: #1f2335;
    color: #7aa2f7;
    padding: 8px 14px;
    margin-right: 3px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 500;
}
QTabBar::tab:selected {
    background: #24283b;
    color: #7dcfff;
    font-weight: bold;
    border-bottom: 2px solid #7aa2f7;
}
QTabBar::tab:hover:!selected {
    background: #292e42;
    color: #c0caf5;
}

/* Modern Kart Şeklinde QGroupBox */
QGroupBox {
    background-color: #1a1e2d;
    border: 1px solid #292e42;
    border-left: 3px solid #7aa2f7;
    border-radius: 8px;
    margin-top: 14px;
    padding: 14px 10px 10px 10px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: 2px;
    padding: 2px 8px;
    color: #7dcfff;
    font-size: 11px;
    font-weight: bold;
    background-color: #16161e;
    border: 1px solid #3b4261;
    border-radius: 4px;
}

QListWidget {
    background-color: #1f2335;
    border: 1px solid #292e42;
    border-radius: 6px;
    padding: 4px;
}
QListWidget::item {
    background-color: #24283b;
    border-radius: 6px;
    margin-bottom: 5px;
    padding: 0px;
}
QListWidget::item:selected {
    background-color: #3b4261;
    border: 1px solid #7aa2f7;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #24283b;
    border: 1px solid #414868;
    border-radius: 6px;
    padding: 5px 8px;
    color: #c0caf5;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #7aa2f7;
    background-color: #1f2335;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #24283b;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #7aa2f7;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #bb9af7;
    width: 14px;
    margin: -4px 0;
    border-radius: 7px;
}
QPushButton {
    background-color: #24283b;
    border: 1px solid #414868;
    color: #c0caf5;
    padding: 6px 12px;
    border-radius: 6px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #3b4261;
    border-color: #7aa2f7;
}

/* Minimalist Koyu Tema Kaydırma Çubuğu (Scrollbar) */
QScrollBar:vertical {
    border: none;
    background: #16161e;
    width: 6px;
    border-radius: 3px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #3b4261;
    min-height: 25px;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: #7aa2f7;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    border: none;
    background: #16161e;
    height: 6px;
    border-radius: 3px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: #3b4261;
    min-width: 25px;
    border-radius: 3px;
}
QScrollBar::handle:horizontal:hover {
    background: #7aa2f7;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
"""

```

## Dosya: ui/tabs/__init__.py
```python

```

## Dosya: update_context.sh
```bash
#!/usr/bin/env bash
cat << 'INNER_EOF' > CONTEXT.md
# TRAY-AI PROJE HAFIZA VE DURUM DÖKÜMANI

## 1. Proje Amacı ve Vizyonu
Linux Mint (ve diğer dağıtımlar) için PyQt6 tabanlı, sistem tepsisinde (system tray) sessizce çalışan, OpenAI ve Ollama API uyumlu hibrit yerel LLM/VLM sunucu yönetim aracı.
- Kullanıcı tek tıkla GGUF modellerini yönetir, bağlam, katman, örnekleyici ve donanım ayarlarını yapar.
- Bağımsız Vulkan/AVX2 destekli `llama-server` sürecini (PID) kontrol eder; ebeveyn ölüm sinyaliyle (PDEATHSIG) zombi süreçleri engeller.
- Dahili STT (Whisper Bas-Konuş) ve Vision (Görsel Analiz) desteği sunar.
- Paketler (.deb ve .rpm) **all-in-one** yapıdadır; kullanıcının harici bağımlılık kurmasına gerek kalmadan motorları içinde barındırır.

## 2. Donanım ve Çalışma Ortamı
- **Geliştirici:** Baybora
- **Ana Sistem:** AMD Ryzen 7 8700G (Radeon 780M iGPU), 96GB DDR5 RAM, AMD Radeon RX 6600 dGPU.
- **İkinci Sistem:** AMD Ryzen 7 5700G, 64GB DDR4 RAM.
- **İşletim Sistemi:** Linux Mint (Saf Linux mimarisi).
- **Hedef:** Düşük maliyetle/mevcut donanımla büyük modelleri (Qwen, DeepSeek vb.) Vulkan hızlandırmasıyla yerelde verimli çalıştırmak.

## 3. Mimari Bileşenler
- `main.py`: PyQt6 sistem tepsisi, tek parça alt konsol (Unified Bottom Dock), model ayar hafızası (persistence), tekerlek koruması (NoWheelEventFilter) ve masaüstü bildirimleri.
- `ui/chat_dialog.py`: Dahili Mini Playground. Canlı düşünce zinciri (Reasoning/Thinking) gösterimi, sürükle-bırak görsel analizi (Vision / VLM) ve anlık TTFT/Hız sayaçları.
- `ui/styles.py`: Koyu tema, sol kenar vurgulu kart panelleri (accent border) ve 6px minimal kaydırma çubukları.
- `core/hardware.py`: Linux `sysfs/drm` bellek arayüzünden kart bazlı anlık VRAM okuma (`read_drm_vram_used_gb`) ve CPU/RAM telemetry.
- `core/api_gateway.py`: OpenAI ve Ollama uyumlu çift protokol HTTP gateway. `BrokenPipeError` ve soket kopmalarına karşı korumalı akış mimarisi.
- `core/server_manager.py`: `llama-server` yönetimi, açılışta zombi süreç temizliği ve Linux `PR_SET_PDEATHSIG` çekirdek takibi.
- `core/gguf_parser.py`: GGUF metadata ayrıştırma, MTP (Multi-Token Prediction) ve YaRN uzun bağlam tespiti.
- `core/hf_downloader.py`: Hugging Face üzerinden sadece LLM/VLM modellerini süzme, arama ve parçalı indirme motoru.
- `core/whisper_manager.py`: ALSA `arecord` ve `whisper-cli` tabanlı yerel bas-konuş sesli asistan motoru.

## 4. Son Eklenen Yetenekler (v1.2 Sprint)
1. **Model Ayar Hafızası:** Modellerin katman, context, sıcaklık, batch ve sampler ayarlarının `config.json` içinde kalıcı saklanması.
2. **No-Wheel Event Koruması:** Sayfa kaydırılırken kutucuk değerlerinin istemsiz değişmesinin engellenmesi.
3. **Canlı Kart Bazlı VRAM Barları:** RX 6600 ve Radeon 780M kartlarının bellek doluluklarının anlık izlenmesi.
4. **Mini Playground (Chat & Vision):** Model düşünce zincirini gösteren ve görsel analizi destekleyen entegre test sohbeti.
5. **Modern Alt Konsol & Çerçevesiz Butonlar:** Telemetri ve model eylem butonlarının tek parça estetik konsolda toplanması.
6. **Masaüstü Bildirimleri:** Model yüklenmesi, indirme tamamlama ve sunucu durumlarının masaüstü balonlarıyla bildirilmesi.
INNER_EOF
chmod +x update_context.sh
echo "✅ update_context.sh güncellendi!"

```
