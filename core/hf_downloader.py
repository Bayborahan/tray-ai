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
    caps = {
        "thinking": False,
        "tools": False,
        "vision": False,
        "audio": False
    }
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
        self.mode = mode  # "trending", "downloads", "likes", "recent", "search"
        self.limit = limit
        self.token = token.strip()

    def run(self):
        try:
            headers = {"User-Agent": "TrayAI/2.0"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            params = {
                "filter": "gguf",
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

            # Tree endpoint dosya boyutlarını doğrudan byte cinsinden verir
            url = f"https://huggingface.co/api/models/{self.repo_id}/tree/main"
            resp = requests.get(url, headers=headers, timeout=12)
            resp.raise_for_status()
            tree = resp.json()

            gguf_files = []
            for node in tree:
                path = node.get("path", "")
                if path.lower().endswith(".gguf"):
                    size_bytes = node.get("size", 0)
                    # LFS altındaysa gerçek boyutu lfs sözlüğünden al
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
    progress = pyqtSignal(str, int, float, float, float) # task_id, pct, dl_mb, total_mb, speed_mb_s
    status_changed = pyqtSignal(str, str) # task_id, status_str
    finished_dl = pyqtSignal(str, str) # task_id, dest_path
    error = pyqtSignal(str, str) # task_id, err_msg

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
