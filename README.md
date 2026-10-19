# 🚀 Tray-AI

A highly advanced GGUF Large Language Model (LLM) runner and server that runs quietly in your Linux system tray, bringing massive capabilities into a minimalist control window.

Tray-AI is designed as a lightweight, performance-oriented, and distraction-free alternative to heavy tools like LM Studio on Linux.

## ✨ Key Features (Including what LM Studio lacks!)

- 📥 **Advanced Model Management:** Search, discover, and download GGUF models directly from Hugging Face with a single click inside the app.
- 📁 **Flexible Directory Support:** Select any local model folder, and Tray-AI will instantly scan and list all your GGUF models.
- 🏎️ **Dual-Engine Support:** Choose between the standard **llama.cpp server** or the high-performance **turboquant-llama.cpp server** to run your models according to your hardware needs.
- 🔄 **In-App Engine Updates:** Easily update your underlying server engines directly from the application interface to get the latest performance tweaks.
- 🐳 **Lightweight & Minimalist:** Sits quietly in your system tray without desktop clutter, dedicating your RAM, CPU, and GPU resources strictly to the model and server.
- 🌐 **Local OpenAI-Compatible API:** Spawns an OpenAI-standard API server instantly. Connect it effortlessly to your code editors (VS Code via Continue, Cursor, etc.), web UIs, or third-party apps in seconds.

## 🛠️ Installation & Quick Start

Tray-AI comes pre-packaged with all its dependencies for a seamless installation. You don't even need Python installed on your system!

### 📦 Option 1: Install via Package Manager (Recommended)

Go to the **[Releases]** page, download the appropriate package for your Linux distribution, and install it:

#### For Ubuntu / Debian / Mint (.deb)
```bash
sudo apt install ./tray-ai_1.0.5_amd64.deb
```

#### For Fedora / RHEL / CentOS (.rpm)
```bash
sudo dnf install ./tray-ai-1.0.5-1.x86_64.rpm
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


## 🚀 How to Use
1. Launch the application; a dedicated icon will appear in your Linux system tray (top/bottom corner depending on your desktop environment).
2. Click the icon to toggle a sleek, compact window where you can manage models, browse Hugging Face, or tweak server settings.
3. Start the server, and it will immediately begin accepting API requests on your designated local port.

## 📜 License
This project is licensed under the **MIT License**. See the `LICENSE` file for more details.
>>>>>>> 3f8ad31c091ae9649c2db54b986c79bdfc4dc929
