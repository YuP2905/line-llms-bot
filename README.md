# line-llms-bot

A FastAPI-based backend service for a LINE Bot, integrating multimodal large language models to provide AI-powered conversations for LINE users.

## 🎯 Core Features

- **LINE Bot Integration** – Receive and process text, image, and video messages from the LINE platform  
- **Multimodal AI Conversation** – Supports understanding and responding to text, images, and videos (currently based on the Qwen3-VL series)  
- **Intelligent Model Selection** – Automatically selects the appropriate model (2B / 4B / 8B / 30B) based on available GPU memory  
- **Session Management** – Maintains user conversation history and context  
- **Security Protection** – Login authentication, IP blacklist, and API documentation protection  

## 🏗️ Architecture

```
line-llms-bot/
├── main.py          # FastAPI entry point: middleware, routing, authentication
├── core/
│ ├── config.py      # Configuration management (Pydantic)
│ └── security.py    # Password hashing (bcrypt)
├── apps/
│ ├── bot/           # LINE Bot module
│ │ ├── urls.py      # Webhook handling, message aggregation
│ │ └── typing.py    # Type definitions
│ └── chat/
│ └── callbacks.py   # inference callbacks
├── services/
│ └── manager.py     # Model manager (load / inference / cleanup)
├── templates/       # HTML templates (login page, etc.)
└── requirements.txt # Python dependencies
```

## 🔧 Tech Stack

| Category | Technology |
|----------|-----------|
| Web Framework | FastAPI + Uvicorn |
| AI Models | Qwen3-VL (2B / 4B / 8B / 30B) |
| Quantization | bitsandbytes (4-bit NF4) |
| LINE SDK | line-bot-sdk |
| Deep Learning | PyTorch + Transformers |
| Security | bcrypt password hashing |

## ⚙️ Workflow

1. A LINE user sends a message → Webhook to `/line-bot-api/webhook`  
2. Message aggregation (merge messages within `SLEEP_TIME = 4s`)  
3. Session management (maintains context, cleans up after 180s timeout)  
4. Qwen model inference (supports multimodal inputs: text, image, video)  
5. Response sent back to LINE  

## 🔒 Security Features

- Login-protected API documentation (`/yupeng-gpt-docs`)  
- IP blacklist support (compatible with Cloudflare/Nginx proxy headers)  
- Secure cookie settings (HttpOnly, Secure, SameSite)  
- LINE Webhook signature verification  

## 💡 Highlights

- **Adaptive Model Selection**: Automatically selects model size based on GPU memory  
- **Message Aggregation**: Merges user messages within 4 seconds to reduce inference calls  
- **Context Management**: Retains the last 3 conversation turns  

## 📋 Environment Configuration

Copy `.env.example` to `.env` and fill in the required values:

```bash
# Required
LOGIN_USER=""                    # Login username
LOGIN_PASSWORD_PlainText=""      # Login password (plain text, will be hashed automatically)
LINE_CHANNEL_SECRET=""           # LINE Channel Secret
LINE_CHANNEL_ACCESS_TOKEN=""     # LINE Channel Access Token
DIFFUSION_MODEL_ID=""            # Image generation model ID
PORT=""                          # Service port

# Optional
MAX_NEW_TOKENS="512"             # Maximum number of generated tokens
DO_SAMPLE="true"                 # Whether to use sampling
TEMPERATURE="0.7"                # Sampling temperature
TOP_P="0.9"                      # Top-p sampling parameter
```

## 🚀 Quick Start
### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run the Service

```bash
python main.py
```

The service runs by default at: http://127.0.0.1:8192

### API Documentation

After login, visit: `http://localhost:8192/yupeng-gpt-docs`

## 🤖 Supported Models

Automatically selected based on GPU memory:

| GPU Memory | Model                     |
| ---------- | ------------------------- |
| < 7GB      | Qwen3-VL-2B-Instruct      |
| 7–14GB     | Qwen3-VL-4B-Instruct      |
| 14–128GB   | Qwen3-VL-8B-Instruct      |
| ≥ 128GB    | Qwen3-VL-30B-A3B-Instruct |

## 📝 License

See the [LICENSE](LICENSE) file for details.
