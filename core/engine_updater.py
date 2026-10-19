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
            m = re.search(r"version:\s*(\d+)\s*\(([a-f0-9]+)\)", out)
            if m:
                return f"b{m.group(1)} ({m.group(2)})"
            m2 = re.search(r"b(\d{4,5})", out)
            if m2:
                return f"b{m2.group(1)}"
            return "Kurulu (Aktif)"
        except Exception:
            return "Kurulu (.so hazır)"

    def run(self):
        info = {
            "local_main": self.get_local_version("llama-server"),
            "local_turbo": self.get_local_version("llama-server-turboquant"),
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
        self.target_type = target_type  # "vulkan", "cpu", "turboquant", "rocm", "cuda"
        self.mode = mode  # "download" veya "build"
        self.asset_url = asset_url
        self.turbo_repo = turbo_repo.strip() or "https://github.com/ggml-org/llama.cpp.git"
        self.turbo_branch = turbo_branch.strip()

    def run(self):
        try:
            os.makedirs(self.engines_dir, exist_ok=True)
            # TurboQuant her zaman kaynak koddan veya kendi özel deposundan derlenir ki llama-server-turboquant olarak çıksın
            if self.target_type == "turboquant" or self.mode == "build" or not self.asset_url:
                self._build_from_source()
            else:
                self._download_and_extract()
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _download_and_extract(self):
        dest_bin_name = "llama-server-turboquant" if self.target_type == "turboquant" else "llama-server"
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
        is_turbo = (self.target_type == "turboquant")
        dest_bin_name = "llama-server-turboquant" if is_turbo else "llama-server"
        build_dir = "/tmp/tray_ai_turbo_build" if is_turbo else "/tmp/tray_ai_llama_build"
        shutil.rmtree(build_dir, ignore_errors=True)

        repo_url = self.turbo_repo if is_turbo else "https://github.com/ggml-org/llama.cpp.git"

        # Eğer yerel bir klasör yolu verildiyse (örn: /home/anonymous/turboquant-llama.cpp) doğrudan oradan kopyala/derle
        if os.path.isdir(repo_url):
            self.progress_msg.emit(15, f"Yerel kaynak klasörü kopyalanıyor: {repo_url}...")
            shutil.copytree(repo_url, build_dir, symlinks=True)
        else:
            self.progress_msg.emit(10, f"Kaynak kod çekiliyor ({repo_url}) -> Hedef: {dest_bin_name}...")
            clone_cmd = ["git", "clone", "--depth", "1"]
            if is_turbo and self.turbo_branch:
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

        if self.target_type in ("vulkan", "turboquant"):
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
            raise FileNotFoundError("Derleme sonrası ikili dosya bulunamadı!")

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
