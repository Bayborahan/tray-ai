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
    for key in ["general.organization", "general.author", "general.base_model.author"]:
        if key in all_kv and str(all_kv[key]).strip():
            return str(all_kv[key]).strip()

    path_low = file_path.lower()
    known_publishers = [
        "unsloth", "bartowski", "thebloke", "mradermacher", 
        "qwen", "deepseek-ai", "meta-llama", "mistralai", "google"
    ]
    for pub in known_publishers:
        if f"/{pub}/" in path_low or f"_{pub}_" in path_low or path_low.endswith(f"-{pub}.gguf"):
            return pub.capitalize()
        if pub in os.path.basename(file_path).lower():
            return pub.capitalize()

    if general_name and "/" in general_name:
        return general_name.split("/")[0].strip()

    return "Bilinmiyor"

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
        "extra_meta": {
            "general_name": "",
            "rope_freq_base": 10000.0,
            "rope_scale": 1.0,
            "rope_scaling_type": "none",
            "yarn_orig_ctx": 4096,
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
                if "yarn" in str(val).lower():
                    info["has_yarn"] = True
            elif k_low.endswith(".rope.scaling.original_context_length") and isinstance(val, (int, float)):
                info["extra_meta"]["yarn_orig_ctx"] = int(val)
                info["has_yarn"] = True
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
            elif "mtp_depth" in k_low or "speculative_layers" in k_low:
                if isinstance(val, (int, float)) and val > 0:
                    info["has_mtp"] = True
                    info["mtp_layers"] = int(val)
            elif k_low.endswith("temperature") and isinstance(val, (int, float)):
                info["recommended_temp"] = float(val)
            elif k_low.endswith("top_p") and isinstance(val, (int, float)):
                info["recommended_topp"] = float(val)
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

        # Tensörlerden MTP kontrolü
        mtp_tensors = 0
        for t in reader.tensors:
            tname = t.name.lower()
            if any(x in tname for x in ["mtp", "nextn", "eh_proj", "shared_head"]):
                mtp_tensors += 1
            if "mmproj" in tname or "vision" in tname:
                info["has_vision"] = True

        if mtp_tensors >= 1:
            info["has_mtp"] = True
            if info["mtp_layers"] == 0:
                info["mtp_layers"] = max(1, mtp_tensors // 2 or 1)

        # YaRN ile genişletilmiş bağlam tespiti
        if info["extra_meta"]["rope_scale"] > 1.0:
            info["has_yarn"] = True

        fn_up = info["filename"].upper()
        for q in ["Q8_0", "Q6_K_L", "Q6_K", "Q5_K_L", "Q5_K_M", "Q5_K_S", "Q4_K_L", "Q4_K_M", "Q4_K_S", "IQ4_XS", "IQ4_NL", "Q3_K_L", "Q3_K_M", "IQ3_M", "Q2_K", "BF16", "F16"]:
            if q in fn_up:
                info["quant"] = q
                break

        fn_low = info["filename"].lower()
        if template_str:
            if any(w in template_str for w in ["<think>", "thought", "reasoning", "think_start"]):
                info["has_thinking"] = True
            if any(w in template_str for w in ["tools", "tool_call", "<tool_call>", "function"]):
                info["has_tools"] = True

        if any(w in fn_low for w in ["qwen3", "qwq", "r1", "thinking", "reasoning", "deepseek"]):
            info["has_thinking"] = True
        if any(w in fn_low for w in ["vl", "vision", "llava", "pixtral", "minicpm-v"]):
            info["has_vision"] = True

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
