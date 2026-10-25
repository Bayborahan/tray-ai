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
