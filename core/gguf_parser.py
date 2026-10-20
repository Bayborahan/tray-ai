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
