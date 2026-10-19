# 🚀 Tray-AI

A high-performance, lightweight GGUF Large Language Model (LLM) runner and server that operates quietly in your Linux system tray, packing comprehensive control into a sleek, minimalist interface.

Tray-AI is designed as an ultra-fast, performance-oriented, and distraction-free native Linux alternative to resource-heavy Electron tools like LM Studio.

---

## ✨ Key Features (What Makes Tray-AI Stand Out)

- ⚡ **Native Hardware Acceleration (Vulkan & AVX2):** Zero-overhead inference powered directly by official `llama.cpp` server binaries compiled with Vulkan and AVX2/AVX-512 instruction sets.
- 📡 **Real-Time Live Telemetry:** Uninterrupted token speed tracking (Tokens/sec), prompt processing progress, and live context utilization without artificial UI freezes during Tool/Agent calls.
- 🧠 **Dynamic Architecture & Metadata Sync:** Automatically detects MTP (Multi-Token Prediction), YaRN context scaling up to 1M tokens, speculative drafting, and optimal sampling temperatures straight from model metadata.
- 🔧 **Native Remote Tool & MCP Support:** Full Jinja template parsing and special token forwarding (`--jinja`, `--special`) for IDE extensions (Cursor, Continue.dev, Cline, Roo Code) and agentic workflows.
- 📥 **Integrated Hugging Face Hub:** Discover, search, filter (Trending, Downloads, Likes), and download quantized GGUF models with resume/pause capabilities directly inside the app.
- 🧹 **One-Click RAM Cache Flush:** Safely clear Linux kernel pagecache and system memory after unloading large models to keep your workstation fresh.
- 🐳 **Minimalist & Resource Conscious:** Sits unobtrusively in your Linux system tray without desktop clutter, dedicating virtually all CPU, RAM, and VRAM strictly to model inference.
- 🌐 **OpenAI-Compatible Local API:** Instantly spawns a standards-compliant `/v1` endpoint for seamless integration with any local or network client.
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
