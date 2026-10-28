# 🚀 Tray-AI

A high-performance, lightweight GGUF Large Language Model (LLM) & Vision (VLM) server operating quietly in your Linux system tray. Packing comprehensive hardware control, an autonomous Linux terminal agent, and dual OpenAI/Ollama APIs into a sleek, minimalist PyQt6 interface.

Tray-AI is engineered as an ultra-fast, performance-oriented, zero-overhead native Linux alternative to resource-heavy Electron tools like LM Studio and Ollama.

---

## ✨ Key Features (What Makes Tray-AI Stand Out)

### 🐧 Autonomous Linux SysAdmin Copilot (In-Chat Terminal Agent)
- **Live Terminal Execution:** Directly inspect, troubleshoot, and monitor your Linux workstation from inside the chat window.
- **Human-in-the-Loop & Sudo Shield:** Safe command execution with one-click approval cards and secure password prompts for `sudo` operations.
- **Autonomous Observation Loop:** Safe inspection commands (`uname`, `free`, `lspci`, `sensors`, `ps`) run automatically on auto-pilot, returning terminal logs directly back into the model's context for instant diagnosis.

### ⚖️ Advanced Asymmetric Multi-GPU & iGPU Load Balancer
- **Main Compute Device Selection (`--main-gpu`):** Delegate compute graphs, scratch buffers, and prompt processing to any specific GPU/APU to keep your primary display buttery smooth.
- **Desktop VRAM Headroom Protection:** Reserve dedicated VRAM (e.g., 2.0–3.0 GB) for your display server (Xorg/Wayland, desktop environments, browsers), ensuring your graphical workspace never freezes or crashes.
- **Intelligent Usable VRAM Matrix (`-ts`):** Proportional layer splitting calculated dynamically from net usable memory across hybrid and asymmetric configurations (e.g., dGPU + iGPU, dual NVIDIA/AMD setups, or mixed VRAM pools).
- **Flexible KV Cache Hosting:** Offload long context buffers directly to System RAM (`-nkvo`) for massive context windows, keeping high-speed VRAM strictly reserved for model weights.

### 🔄 Infinite Context Crash Prevention & Instant Presets
- **Crash-Proof Context Shifting (`--context-shift`):** Seamlessly handles 131K–262K+ context limits via intelligent sliding window eviction—preventing sudden `llama-server` process aborts or slot exhaustion crashes.
- **One-Click Sampler Presets:** Instantly switch between tuned configurations:
  - 🎯 **Deterministic Coding:** Low temperature, strict repetition penalties.
  - 🧠 **Deep Reasoning:** Tuned for Qwen3, DeepSeek-R1, and thinking models.
  - 🎭 **Creative Chat & Roleplay:** Enabled DRY, XTC, and dynamic temperature.
  - 🤖 **Structured JSON / Tool Calling:** Zero-temp deterministic output for MCP and agents.

### 💬 Modern Chat Playground (Vision, Thinking & Markdown)
- **Messaging App Bubble Layout:** Distinct user (right) and assistant (left) cards.
- **Dedicated Thinking Process Box:** Collapsible and visually isolated `💭 Reasoning` cards for models with `<think>` streams.
- **Drag-and-Drop Multimodal Vision:** Drop any image (PNG, JPG, WEBP) into the chat for instant visual reasoning with compatible VLMs (`--mmproj`).
- **Markdown Export:** Export your complete multi-turn discussions and troubleshooting logs directly into `.md` files.

### ⚡ Resumable 4-Thread Hugging Face Engine
- **Segmented Fast Downloader:** 4 parallel download streams utilizing byte-range requests with instant pause/resume across system reboots via persistent `.state.json` trackers.
- **Integrity & GGUF Validation:** Automatic SHA-256 hash checks and GGUF header validation prior to finalizing models.
- **Organized Hierarchy:** Clean publisher/model structure (`publisher/model/quant.gguf`).

### 🌐 Dual Protocol API Gateway & System Integrations
- **OpenAI & Ollama Compatible (`:8080`):** Out-of-the-box compatibility with Cursor, Continue.dev, Cline, Open WebUI, and standard Ollama CLI workflows.
- **🎙️ Local Whisper Bas-Konuş:** Integrated voice assistant powered by native `whisper-cli`.
- **🧹 One-Click RAM Cache Flush:** Clean Linux kernel pagecache and system memory after unloading large models.
- **📦 All-in-One Linux Packages:** Zero runtime dependencies—pre-compiled Vulkan & AVX2 `llama.cpp` engines bundled directly into `.deb` and `.rpm` packages.


## 🛠️ Installation & Quick Start

Tray-AI comes pre-packaged with all its dependencies for a seamless installation. You don't even need Python installed on your system!

### 📦 Option 1: Install via Package Manager (Recommended)

Go to the **[Releases]** page, download the appropriate package for your Linux distribution, and install it:

#### For Ubuntu / Debian / Mint (.deb)
```bash
sudo apt install ./tray-ai_amd64.deb
```

#### For Fedora / RHEL / CentOS (.rpm)
```bash
sudo dnf install ./tray-ai_x86_64.rpm
```

Once installed, you can launch the app directly from your application menu or by simply typing `tray-ai` in your terminal.

---

### 🚀 Option 2: Run the Portable Executable

If you don't want to install anything, just download the standalone binary `Tray-AI-Linux-x86_64` from the Releases page, make it executable, and run it:

```bash
chmod +x Tray-AI-Linux-x86_64
./Tray-AI-Linux-x86_64
```

---

### 👨‍💻 Option 3: For Developers (From Source)

If you prefer to run it directly from the source code:

1. Ensure you have Python 3 installed and clone the repository.
2. Install the required python dependencies:
```bash
pip install -r requirements.txt
```
3. Launch the application:
```bash
python main.py
```

```bash
./run.sh
```

## 🚀 How to Use
1. Launch the application; a dedicated icon will appear in your Linux system tray (top/bottom corner depending on your desktop environment).
2. Click the icon to toggle a sleek, compact window where you can manage models, browse Hugging Face, or tweak server settings.
3. Start the server, and it will immediately begin accepting API requests on your designated local port.

## 📜 License
This project is licensed under the **MIT License**. See the `LICENSE` file for more details.

