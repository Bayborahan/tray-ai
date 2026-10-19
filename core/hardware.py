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
