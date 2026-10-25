import psutil
import subprocess
import os
import re

def get_drm_card_map():
    card_map = {}
    drm_base = "/sys/class/drm"
    if not os.path.exists(drm_base):
        return card_map

    for c in os.listdir(drm_base):
        if re.match(r"^card\d+$", c):
            try:
                c_idx = int(c.replace("card", ""))
            except ValueError:
                continue

            dev_dir = f"{drm_base}/{c}/device"
            if not os.path.exists(dev_dir):
                continue

            v_tot = 0
            g_tot = 0
            try:
                with open(f"{dev_dir}/mem_info_vram_total", "r") as f:
                    v_tot = int(f.read().strip())
            except Exception:
                pass
            try:
                with open(f"{dev_dir}/mem_info_gtt_total", "r") as f:
                    g_tot = int(f.read().strip())
            except Exception:
                pass

            pci_slot = ""
            uevent_file = f"{dev_dir}/uevent"
            if os.path.exists(uevent_file):
                try:
                    with open(uevent_file, "r") as f:
                        for line in f:
                            if line.startswith("PCI_SLOT_NAME="):
                                pci_slot = line.strip().split("=")[1]
                                break
                except Exception:
                    pass

            c_name = ""
            if pci_slot:
                try:
                    out = subprocess.check_output(["lspci", "-s", pci_slot], text=True, stderr=subprocess.DEVNULL)
                    c_name = out.strip()
                except Exception:
                    pass

            is_igpu = (v_tot < 4 * (1024**3))
            card_map[c_idx] = {
                "card_idx": c_idx,
                "pci_slot": pci_slot,
                "name": c_name,
                "is_igpu": is_igpu,
                "vram_total_gb": round(v_tot / (1024**3), 2),
                "gtt_total_gb": round(g_tot / (1024**3), 2)
            }
    return card_map

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
    except Exception:
        pass

    drm_cards = get_drm_card_map()
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
                m = re.match(r"^\s*((?:Vulkan|ROCm|HIP|CUDA|Metal|SYCL)\d+)\s*:\s*(.+?)\s*\((\d+)\s*MiB", line, re.IGNORECASE)
                if m:
                    dev_id_str = m.group(1).strip()
                    dev_name = m.group(2).strip()
                    vram_mib = int(m.group(3))

                    idx_match = re.search(r"(\d+)$", dev_id_str)
                    dev_idx = int(idx_match.group(1)) if idx_match else len(gpus)
                    backend = re.sub(r"\d+$", "", dev_id_str)

                    dedup_key = f"{dev_idx}_{dev_name.lower()}"
                    if dedup_key in seen_keys or dev_id_str.lower() in seen_keys:
                        continue
                    seen_keys.add(dedup_key)
                    seen_keys.add(dev_id_str.lower())

                    # Gerçek DRM Card'ı akıllı eşleştir
                    matched_drm = dev_idx
                    matched_is_igpu = False
                    d_low = dev_name.lower()

                    for c_idx, c_info in drm_cards.items():
                        c_n = c_info["name"].lower()
                        if ("780m" in d_low or "graphics" in d_low) and c_info["is_igpu"]:
                            matched_drm = c_idx
                            matched_is_igpu = True
                            break
                        elif "6600" in d_low and not c_info["is_igpu"]:
                            matched_drm = c_idx
                            matched_is_igpu = False
                            break

                    # Eğer Vulkan adı doğrudan eşleşmediyse fallback
                    if matched_drm not in drm_cards and dev_idx in drm_cards:
                        matched_drm = dev_idx
                        matched_is_igpu = drm_cards[dev_idx]["is_igpu"]

                    gpus.append({
                        "id": dev_idx,
                        "drm_card": matched_drm,
                        "is_igpu": matched_is_igpu,
                        "backend_id": dev_id_str,
                        "name": dev_name,
                        "vram_gb": round(vram_mib / 1024.0, 2),
                        "backend": backend
                    })
        except Exception:
            pass

    if not gpus:
        for c_idx, c_info in drm_cards.items():
            gpus.append({
                "id": c_idx,
                "drm_card": c_idx,
                "is_igpu": c_info["is_igpu"],
                "backend_id": f"Device{c_idx}",
                "name": c_info["name"] or f"GPU {c_idx}",
                "vram_gb": c_info["gtt_total_gb"] if c_info["is_igpu"] else c_info["vram_total_gb"],
                "backend": "GPU"
            })

    total_vram_gb = round(sum(g["vram_gb"] for g in gpus), 2)

    return {
        "cpu_name": cpu_name,
        "cpu_arch": cpu_arch,
        "cpu_flags": cpu_flags,
        "ram_gb": total_ram_gb,
        "total_vram_gb": total_vram_gb,
        "gpus": gpus
    }

def read_drm_vram_used_gb(card_idx, is_igpu=None):
    dev_dir = f"/sys/class/drm/card{card_idx}/device"
    vram_used_file = f"{dev_dir}/mem_info_vram_used"
    gtt_used_file = f"{dev_dir}/mem_info_gtt_used"
    vram_tot_file = f"{dev_dir}/mem_info_vram_total"

    vram_used_b = 0
    gtt_used_b = 0
    vram_tot_b = 0

    try:
        if os.path.exists(vram_used_file):
            with open(vram_used_file, "r") as f:
                vram_used_b = int(f.read().strip())
    except Exception:
        pass

    try:
        if os.path.exists(gtt_used_file):
            with open(gtt_used_file, "r") as f:
                gtt_used_b = int(f.read().strip())
    except Exception:
        pass

    try:
        if os.path.exists(vram_tot_file):
            with open(vram_tot_file, "r") as f:
                vram_tot_b = int(f.read().strip())
    except Exception:
        pass

    if is_igpu is None:
        is_igpu = (vram_tot_b < 4 * (1024**3))

    if is_igpu:
        # APU / iGPU (Radeon 780M): Model tensörleri GTT (paylaşılan RAM) havuzundadır.
        total_used_b = vram_used_b + gtt_used_b
        return round(total_used_b / (1024**3), 2)
    else:
        # Ayrık GPU (RX 6600): Fiziksel VRAM'i baz al
        return round(vram_used_b / (1024**3), 2)
