# InstaBOT

[![中文](https://img.shields.io/badge/-%E4%B8%AD%E6%96%87-red)](README_CN.md)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python)](https://www.python.org/)
[![Instagram](https://img.shields.io/badge/Instagram-API-ff69b4?logo=instagram)](https://www.instagram.com/)
[![Firebase](https://img.shields.io/badge/Firebase-Realtime-orange?logo=firebase)](https://firebase.google.com/)
[![Supabase](https://img.shields.io/badge/Supabase-Database-green?logo=supabase)](https://supabase.com/)
[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-CI%2FCD-2088FF?logo=github-actions)](https://github.com/features/actions)
[![Cloudflare](https://img.shields.io/badge/Cloudflare-Workers-F38020?logo=cloudflare)](https://workers.cloudflare.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Your intelligent Instagram companion that feels like chatting with a real friend. It remembers your conversations, understands context, and even helps you keep a diary of your daily interactions.

## What makes it special?

- **Natural Conversations**: Chat like you're talking to a real friend. The bot remembers your previous conversations and responds contextually.
- **Automatic Diary**: Your chats are automatically organized into a daily diary, complete with mood analysis and weather records.
- **Smart & Safe**: Designed to behave naturally while keeping your account secure.

## Technical Overview

Built with modern technologies:
- Firebase for conversation history
- Supabase for diary storage
- Multiple AI models (Gemini Pro/Flash)
- GitHub Actions for automation
- Cloudflare Workers for reliable triggering

## Getting Started

### Prerequisites

You'll need Base64 encoded versions of:
1. Firebase credentials (from your serviceAccount.json)
2. Instagram session file (after first login)
3. Proxy configuration (if needed)

### Environment Variables

Essential variables to configure:
```bash
# Instagram
INSTAGRAM_USERNAME=your_username
INSTAGRAM_PASSWORD=your_password
INSTAGRAM_SESSION=base64_encoded_session

# API Keys
GEMINI_API_KEY=your_key
LINGYI_API_KEY=your_key

# Database
FIREBASE_CREDENTIALS_BASE64=base64_encoded_credentials
FIREBASE_DATABASE_URL=your_url
SUPABASE_URL=your_url
SUPABASE_KEY=your_key

# Security
CHAT_HISTORY_KEY=your_key
ENCRYPTION_KEY=your_key
```

### Running the Bot

You can trigger the bot in three ways:
1. Manual trigger through GitHub Actions
2. Scheduled runs
3. Via Cloudflare Worker (recommended for reliability)

For detailed Worker setup, check [Worker Setup Guide](docs/worker_setup.md)

## Privacy & Security

Your conversations are encrypted and stored securely. The bot follows Instagram's usage guidelines and includes safety measures to protect your account.

---

# InstaBOT (中文版)

这是一个智能 Instagram 助手，它就像一个真实的朋友，能与你自然对话，记住你们的交谈，还能帮你记录每天的生活点滴。

## 特色功能

- **自然对话**：像与真实朋友聊天一样，它能记住你们的对话，理解上下文。
- **自动日记**：自动整理你们的对话，记录心情变化和天气。
- **智能安全**：模拟真实用户行为，确保账号安全。

## 开始使用

### 准备工作

你需要准备以下内容的 Base64 编码：
1. Firebase 凭证
2. Instagram 会话文件
3. 代理配置（如需要）

### 环境变量

主要配置项：
```bash
# Instagram 配置
INSTAGRAM_USERNAME=你的用户名
INSTAGRAM_PASSWORD=你的密码
INSTAGRAM_SESSION=base64编码的会话

# API 密钥
GEMINI_API_KEY=你的密钥
LINGYI_API_KEY=你的密钥

# 数据库配置
FIREBASE_CREDENTIALS_BASE64=base64编码的凭证
FIREBASE_DATABASE_URL=你的URL
SUPABASE_URL=你的URL
SUPABASE_KEY=你的密钥

# 安全配置
CHAT_HISTORY_KEY=你的密钥
ENCRYPTION_KEY=你的密钥
```

详细的 Worker 配置说明请查看 [Worker 配置指南](docs/worker_setup.md)

## 隐私与安全

所有对话都经过加密存储，机器人严格遵循 Instagram 使用规范，并采取多重措施保护账号安全。 