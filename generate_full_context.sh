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
