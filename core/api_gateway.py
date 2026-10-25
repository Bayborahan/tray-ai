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
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With, Accept, Origin, *")
        self.send_header("Access-Control-Max-Age", "86400")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        clean_path = parsed.path.rstrip("/").lower()

        if clean_path in ("/api/version", "/version"):
            resp = json.dumps({"version": "0.5.4"}).encode("utf-8")
            self._send_json_response(200, resp)
            return

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

        if clean_path in ("", "/health"):
            resp = b'{"status": "ok", "service": "Tray-AI Gateway"}'
            self._send_json_response(200, resp)
            return

        self._proxy_request("GET")

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len > 0 else b""

        parsed = urlparse(self.path)
        clean_path = parsed.path.rstrip("/").lower()

        if clean_path in ("/api/show", "/show"):
            try:
                p_data = json.loads(body.decode("utf-8")) if body else {}
                m_name = p_data.get("name", p_data.get("model", ""))
                if m_name.endswith(":latest"):
                    m_name = m_name[:-7]
                resp = json.dumps({
                    "modelfile": f"# Modelfile for {m_name}\nFROM {m_name}",
                    "parameters": "temperature 0.7",
                    "template": "{{ .Prompt }}",
                    "details": {"format": "gguf", "family": "llama"}
                }).encode("utf-8")
                self._send_json_response(200, resp)
                return
            except Exception:
                pass

        if clean_path in ("/api/chat", "/api/generate"):
            self._handle_ollama_inference(clean_path, body)
            return

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

        self._ensure_model_loaded(model_name)

        upstream_port = self.server.gateway_ref.upstream_port
        iso_now = datetime.now(timezone.utc).isoformat()

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

        options = payload.get("options", {})
        for opt in ["temperature", "top_p", "top_k"]:
            if opt in options:
                openai_payload[opt] = options[opt]

        upstream_url = f"http://127.0.0.1:{upstream_port}/v1/chat/completions"

        if is_stream:
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Cache-Control", "no-cache")
            self._send_cors_headers()
            self.end_headers()

            try:
                resp = requests.post(upstream_url, json=openai_payload, stream=True, timeout=300)
                for line in resp.iter_lines():
                    if not line:
                        continue
                    line_str = line.decode("utf-8", errors="replace").strip()
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
                                data_bytes = (json.dumps(nd_chunk, ensure_ascii=False) + "\n").encode("utf-8")
                                self._write_http_chunk(data_bytes)
                        except Exception:
                            pass

                if path == "/api/generate":
                    done_chunk = {"model": raw_model, "created_at": iso_now, "response": "", "done": True}
                else:
                    done_chunk = {"model": raw_model, "created_at": iso_now, "message": {"role": "assistant", "content": ""}, "done": True}
                self._write_http_chunk((json.dumps(done_chunk, ensure_ascii=False) + "\n").encode("utf-8"))
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except Exception:
                pass
        else:
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
            
            start_t = time.time()
            time.sleep(1.0)
            while time.time() - start_t < 120:
                if self._check_engine_ready(upstream_port):
                    return
                time.sleep(0.5)

    def _check_engine_ready(self, port):
        try:
            r = requests.get(f"http://127.0.0.1:{port}/health", timeout=0.4)
            return r.status_code == 200 and r.json().get("status") == "ok"
        except Exception:
            return False

    def _write_http_chunk(self, data):
        if not data:
            return
        chunk_header = f"{len(data):X}\r\n".encode("ascii")
        self.wfile.write(chunk_header + data + b"\r\n")
        self.wfile.flush()

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

            is_streaming = (
                "text/event-stream" in resp.headers.get("content-type", "").lower() or
                resp.headers.get("transfer-encoding", "").lower() == "chunked" or
                "application/x-ndjson" in resp.headers.get("content-type", "").lower()
            )

            cors_keys = {
                "access-control-allow-origin", "access-control-allow-methods",
                "access-control-allow-headers", "access-control-max-age",
                "access-control-allow-credentials", "access-control-expose-headers"
            }

            self.send_response(resp.status_code)
            for k, v in resp.headers.items():
                k_low = k.lower()
                if k_low in ("content-length", "transfer-encoding", "content-encoding", "connection") or k_low in cors_keys:
                    continue
                self.send_header(k, v)

            self._send_cors_headers()

            if is_streaming:
                self.send_header("Transfer-Encoding", "chunked")
                self.send_header("Connection", "keep-alive")
                self.end_headers()

                for chunk in resp.iter_content(chunk_size=512):
                    if chunk:
                        try:
                            self._write_http_chunk(chunk)
                        except (BrokenPipeError, ConnectionResetError):
                            return
                try:
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()
                except Exception:
                    pass
            else:
                full_content = resp.content
                self.send_header("Content-Length", str(len(full_content)))
                self.end_headers()
                self.wfile.write(full_content)
                self.wfile.flush()

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
