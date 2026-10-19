**🚀 Tray-AI**  
A highly advanced GGUF Large Language Model (LLM) runner and server that runs quietly in your Linux system tray, bringing massive capabilities into a minimalist control window.  
Tray-AI is designed as a lightweight, performance-oriented, and distraction-free alternative to heavy tools like LM Studio on Linux.  
**✨ Key Features (Including what LM Studio lacks!)**  
- 📥 **Advanced Model Management:** Search, discover, and download GGUF models directly from Hugging Face with a single click inside the app.  
- 📁 **Flexible Directory Support:** Select any local model folder, and Tray-AI will instantly scan and list all your GGUF models.  
- 🏎️ **Dual-Engine Support:** Choose between the standard  **llama.cpp server** or the high-performance  **turboquant-llama.cpp server** to run your models according to your hardware needs.  
- 🔄 **In-App Engine Updates:** Easily update your underlying server engines directly from the application interface to get the latest performance tweaks.  
- 🐳 **Lightweight & Minimalist:** Sits quietly in your system tray without desktop clutter, dedicating your RAM, CPU, and GPU resources strictly to the model and server.  
- 🌐 **Local OpenAI-Compatible API:** Spawns an OpenAI-standard API server instantly. Connect it effortlessly to your code editors (VS Code via Continue, Cursor, etc.), web UIs, or third-party apps in seconds.  
**🛠️ Installation & Quick Start**  
**1. Requirements**  
Ensure you have Python and the required dependencies installed on your system:  
pip install -r requirements.txt  
   
**2. Running the Application**  
python3 main.py  
   
./run.sh  


**🚀 How to Use**  
1. Launch the application; a dedicated icon will appear in your Linux system tray (top/bottom corner depending on your desktop environment).  
2. Click the icon to toggle a sleek, compact window where you can manage models, browse Hugging Face, or tweak server settings.  
3. Start the server, and it will immediately begin accepting API requests on your designated local port.  
**📜 License**  
This project is licensed under the **MIT License**. See the LICENSE file for more details.  
