# Uni-Chatbot

A Telegram chatbot that answers questions about campus locations, locker hours, servery hours, FAQs, and AI-powered QA — all packaged in Docker.

---

## Prerequisites

- **Docker** & **Docker Compose** installed  
- A **Telegram bot token** (from [@BotFather](https://t.me/BotFather))  
- A **Mistral AI API key**

---

## Setup & Run

1. Clone the repo:
   ```bash
   git clone https://github.com/your-org/AI-ChatBot-Uni.git
   cd AI-ChatBot-Uni
2. Create a .env in the project root (Golden_Standard) with the tokens:
   ```bash
   TELEGRAM_TOKEN=<your-telegram-bot-token>
   MISTRAL_API_KEY=<your-mistral-api-key>
   HF_TOKEN=<your_hf_token>
3. Build and start services:
   ```bash
   docker compose up --build
4. Open Telegram, find the bot and ask questions:
   - Locker hours: locker hours mercator a
   - Servery hours: servery hours krupp b
   - Campus Map: /where Ocean Lab
   - Residence Permit, etc.
   
