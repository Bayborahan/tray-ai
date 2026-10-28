import os
import re
import time
import json
import hashlib
import requests
from concurrent.futures import ThreadPoolExecutor
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

def extract_model_scale(model_id):
    m_low = model_id.lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*b", m_low)
    if m:
        try:
            val = float(m.group(1))
            if val < 8:
                return "light"
            elif val <= 14:
                return "medium"
            elif val <= 35:
                return "heavy"
            else:
                return "massive"
        except Exception:
            pass
    return "unknown"


class HFSearchWorker(QThread):
    results_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, query="", mode="trending", limit=30, token="", author="", scale_filter="all"):
        super().__init__()
        self.query = query.strip()
        self.mode = mode
        self.limit = limit
        self.token = token.strip()
        self.author = author.strip()
        self.scale_filter = scale_filter

    def run(self):
        try:
            headers = {"User-Agent": "TrayAI/2.0"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            params = {
                "filter": "gguf",
                "pipeline_tag": "text-generation",
                "limit": self.limit,
                "full": "true"
            }

            if self.author and self.author != "all":
                params["author"] = self.author

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
                m_low = mid.lower()
                if any(x in m_low for x in ["bge-", "embed", "flux", "diffusion", "stable-diffusion"]):
                    continue

                scale = extract_model_scale(mid)
                if self.scale_filter != "all" and scale != "unknown" and scale != self.scale_filter:
                    continue

                tags = item.get("tags", [])
                caps = detect_capabilities_from_tags_and_name(mid, tags)
                results.append({
                    "id": mid,
                    "downloads": item.get("downloads", 0),
                    "likes": item.get("likes", 0),
                    "trending": item.get("trendingScore", 0),
                    "scale": scale,
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
                    sha256 = ""
                    if "lfs" in node and isinstance(node["lfs"], dict):
                        size_bytes = node["lfs"].get("size", size_bytes)
                        sha256 = node["lfs"].get("oid", "")

                    size_gb = round(size_bytes / (1024 ** 3), 2) if size_bytes > 0 else 0.0
                    quant = extract_quant_from_filename(path)
                    dl_url = f"https://huggingface.co/{self.repo_id}/resolve/main/{path}"
                    gguf_files.append({
                        "filename": os.path.basename(path),
                        "rel_path": path,
                        "size_gb": size_gb,
                        "size_bytes": size_bytes,
                        "sha256": sha256,
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
    verification_msg = pyqtSignal(str, str)

    def __init__(self, task_id, url, dest_path, token="", expected_sha256="", num_threads=4):
        super().__init__()
        self.task_id = task_id
        self.url = url
        self.dest_path = dest_path
        self.token = token.strip()
        self.expected_sha256 = expected_sha256.strip().lower()
        self.num_threads = max(1, num_threads)
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
        part_path = self.dest_path + ".part"
        state_path = self.dest_path + ".state.json"

        try:
            self.status_changed.emit(self.task_id, "downloading")
            headers = {"User-Agent": "TrayAI/2.0"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"

            total_size = 0
            accept_ranges = False

            # Önce HEAD ile dosya boyutunu ve Range desteğini sorgula
            try:
                head_resp = requests.head(self.url, headers=headers, allow_redirects=True, timeout=15)
                if head_resp.status_code in (200, 206):
                    total_size = int(head_resp.headers.get("content-length", 0))
                    accept_ranges = "bytes" in head_resp.headers.get("accept-ranges", "").lower()
            except Exception:
                pass

            if total_size <= 0:
                with requests.get(self.url, headers=headers, stream=True, timeout=15) as r:
                    r.raise_for_status()
                    total_size = int(r.headers.get("content-length", 0))
                    accept_ranges = "bytes" in r.headers.get("accept-ranges", "").lower()

            # Eğer Range desteklenmiyorsa veya dosya küçükse klasik tek akışla indir
            if not accept_ranges or total_size < 10 * 1024 * 1024:
                self._run_single_thread(part_path, total_size, headers)
            else:
                self._run_multi_threaded(part_path, state_path, total_size, headers)

            if self._is_cancelled or self._is_paused:
                return

            # ========================================================
            # BÜTÜNLÜK VE GGUF FORMAT DOĞRULAMA (VERIFICATION)
            # ========================================================
            self.status_changed.emit(self.task_id, "verifying")
            self.progress.emit(self.task_id, 100, total_size / (1024*1024), total_size / (1024*1024), 0.0)

            if self.expected_sha256:
                hasher = hashlib.sha256()
                with open(part_path, "rb") as f:
                    while chunk := f.read(8 * 1024 * 1024):
                        if self._is_cancelled:
                            return
                        hasher.update(chunk)
                calc_hash = hasher.hexdigest().lower()
                if calc_hash != self.expected_sha256:
                    raise ValueError(f"SHA-256 Uyuşmazlığı! Beklenen: {self.expected_sha256[:12]}... Hesaplanan: {calc_hash[:12]}...")

            # GGUF Başlık Sağlamlık Kontrolü
            try:
                from gguf import GGUFReader
                reader = GGUFReader(part_path)
                if len(reader.fields) < 3:
                    raise ValueError("GGUF metaveri anahtar tablosu boş veya eksik!")
            except Exception as ge:
                raise ValueError(f"GGUF Başlık Hatası: {ge}")

            # Doğrulama başarılı! Dosyayı son yerine taşı
            if os.path.exists(state_path):
                os.remove(state_path)
            os.replace(part_path, self.dest_path)

            self.status_changed.emit(self.task_id, "completed")
            self.finished_dl.emit(self.task_id, self.dest_path)

        except Exception as e:
            self.error.emit(self.task_id, str(e))

    def _run_multi_threaded(self, part_path, state_path, total_size, headers):
        parts = []
        if os.path.exists(state_path) and os.path.exists(part_path):
            try:
                with open(state_path, "r", encoding="utf-8") as sf:
                    st = json.load(sf)
                    if st.get("total_size") == total_size and len(st.get("parts", [])) == self.num_threads:
                        parts = st["parts"]
            except Exception:
                parts = []

        if not parts:
            fd = os.open(part_path, os.O_RDWR | os.O_CREAT)
            os.ftruncate(fd, total_size)
            os.close(fd)

            chunk_size = total_size // self.num_threads
            for i in range(self.num_threads):
                s = i * chunk_size
                e = (total_size - 1) if i == self.num_threads - 1 else ((i + 1) * chunk_size - 1)
                parts.append({"id": i, "start": s, "current": s, "end": e})

        fd = os.open(part_path, os.O_RDWR)

        def _worker(p_idx):
            p = parts[p_idx]
            if p["current"] > p["end"]:
                return
            h = headers.copy()
            h["Range"] = f"bytes={p['current']}-{p['end']}"
            try:
                with requests.get(self.url, headers=h, stream=True, timeout=25) as r:
                    r.raise_for_status()
                    for chunk in r.iter_content(chunk_size=512 * 1024):
                        if self._is_cancelled or self._is_paused:
                            break
                        if chunk:
                            os.pwrite(fd, chunk, p["current"])
                            p["current"] += len(chunk)
            except Exception as ex:
                if not (self._is_cancelled or self._is_paused):
                    raise ex

        last_emit = time.time()
        last_dl = sum(p["current"] - p["start"] for p in parts)

        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            futures = [executor.submit(_worker, i) for i in range(self.num_threads)]

            while True:
                if self._is_cancelled or self._is_paused:
                    break
                done_cnt = sum(1 for f in futures if f.done())
                tot_dl = sum(p["current"] - p["start"] for p in parts)
                now = time.time()
                dt = max(0.05, now - last_emit)

                if dt >= 0.3 or tot_dl >= total_size:
                    spd = ((tot_dl - last_dl) / (1024 * 1024)) / dt
                    pct = int((tot_dl / total_size) * 100) if total_size > 0 else 0
                    self.progress.emit(self.task_id, pct, tot_dl / (1024*1024), total_size / (1024*1024), max(0.0, spd))
                    last_emit = now
                    last_dl = tot_dl

                if done_cnt == self.num_threads:
                    break
                time.sleep(0.15)

            # Olası iş parçacığı hatalarını yakala
            for f in futures:
                if f.done() and f.exception() and not (self._is_cancelled or self._is_paused):
                    os.close(fd)
                    raise f.exception()

        os.close(fd)

        # Durum dosyasını kaydet
        if not self._is_cancelled:
            with open(state_path, "w", encoding="utf-8") as sf:
                json.dump({"total_size": total_size, "parts": parts}, sf)

        if self._is_cancelled:
            if os.path.exists(part_path): os.remove(part_path)
            if os.path.exists(state_path): os.remove(state_path)
            self.status_changed.emit(self.task_id, "cancelled")

    def _run_single_thread(self, part_path, total_size, headers):
        downloaded = os.path.getsize(part_path) if os.path.exists(part_path) else 0
        if downloaded > 0:
            headers["Range"] = f"bytes={downloaded}-"

        mode = "ab" if downloaded > 0 else "wb"
        last_emit = time.time()
        last_dl = downloaded

        with open(part_path, mode) as f:
            with requests.get(self.url, headers=headers, stream=True, timeout=25) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if self._is_cancelled:
                        f.close()
                        if os.path.exists(part_path): os.remove(part_path)
                        self.status_changed.emit(self.task_id, "cancelled")
                        return
                    while self._is_paused:
                        self.msleep(250)
                        if self._is_cancelled:
                            f.close()
                            if os.path.exists(part_path): os.remove(part_path)
                            self.status_changed.emit(self.task_id, "cancelled")
                            return
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        now = time.time()
                        dt = max(0.05, now - last_emit)
                        if dt >= 0.3:
                            spd = ((downloaded - last_dl) / (1024 * 1024)) / dt
                            pct = int((downloaded / total_size) * 100) if total_size > 0 else 0
                            self.progress.emit(self.task_id, pct, downloaded / (1024*1024), total_size / (1024*1024), spd)
                            last_emit = now
                            last_dl = downloaded
