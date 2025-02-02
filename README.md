# InstaBOT - 你的智能生活伙伴

一个基于 Instagram 的智能助手，它不仅是你的好朋友，还能帮你记录生活、整理日记。

## 🌟 主要功能

### 1. 智能对话
- 像真实朋友一样自然交谈
- 记住你们的对话内容
- 根据上下文智能回复
- 支持多种话题延续

### 2. 自动日记
- 每天自动整理你们的对话
- 生成有温度的日记内容
- 记录天气、心情变化
- 支持情感分析
- 云端安全存储

### 3. 智能行为
- 模拟真实用户行为
- 自动浏览感兴趣内容
- 动态调整互动频率
- 保护账号安全

## 🛠 技术特点

- 使用 Firebase 存储对话历史
- Supabase 保存生成的日记
- 多重 AI 模型支持（Gemini Pro/Flash）
- 自动化工作流（GitHub Actions）
- 完整的异常处理机制
- 智能的上下文管理

## 📋 前置准备

在配置环境变量之前，你需要准备以下内容的 Base64 编码：

### 1. Firebase 凭证
- 从 Firebase 控制台下载的 serviceAccount.json 文件
- 需要转换为 Base64 格式
- 用于 `FIREBASE_CREDENTIALS_BASE64` 环境变量

### 2. Instagram 会话
- 首次登录成功后生成的 session.json 文件
- 需要转换为 Base64 格式
- 用于自动化部署时免登录

### 3. 代理配置（如需要）
- 代理服务器配置信息
- 需要转换为 Base64 格式
- 用于网络访问加速

### Base64 编码要求
- 使用标准 Base64 编码（不含换行符）
- 编码前检查文件格式是否正确
- 建议本地完成编码后再配置
- 定期更新以确保安全性

## 🔧 配置说明

### 1. 环境变量列表

以下是所有需要配置的环境变量，请注意标注为 [Base64] 的变量需要进行 Base64 编码：

#### Instagram 相关
- `INSTAGRAM_USERNAME`: Instagram 用户名
- `INSTAGRAM_PASSWORD`: Instagram 密码
- `INSTAGRAM_SESSION`: [Base64] Instagram 会话文件内容

#### 数据库配置
- `FIREBASE_CREDENTIALS_BASE64`: [Base64] Firebase 服务账号凭证
- `FIREBASE_DATABASE_URL`: Firebase 实时数据库 URL
- `SUPABASE_URL`: Supabase 项目 URL
- `SUPABASE_KEY`: Supabase 项目密钥

#### AI API 配置
- `GEMINI_API_KEY`: Google Gemini API 密钥
- `LINGYI_API_KEY`: 灵医万物 API 密钥
- `LINGYI_API_BASE`: 灵医万物 API 基础 URL

#### 加密和安全
- `CHAT_HISTORY_KEY`: 聊天历史加密密钥
- `ENCRYPTION_KEY`: 通用加密密钥
- `HUB_TOKEN`: GitHub Personal Access Token

#### 代理配置（可选）
- `PROXY_CONFIG`: [Base64] 代理服务器配置信息

### 2. Base64 编码说明

需要进行 Base64 编码的文件/内容：
1. `FIREBASE_CREDENTIALS_BASE64`
   - 源文件：从 Firebase 控制台下载的 serviceAccount.json
   - 用途：Firebase 身份验证

2. `INSTAGRAM_SESSION`
   - 源文件：首次登录后生成的 session.json
   - 用途：免登录自动化运行

3. `PROXY_CONFIG`（如需要）
   - 源内容：代理服务器配置信息
   - 格式示例：
   ```json
   {
     "host": "proxy.example.com",
     "port": 1080,
     "username": "user",
     "password": "pass"
   }
   ```

### 3. 运行环境
- Python 3.12+
- 依赖包见 `requirements.txt`

## 📝 日记功能说明

每天的日记会包含：
- 当天的天气情况
- 对话内容梳理
- 情感状态分析
- 主要事件记录
- 个人感悟总结

## 🤖 机器人特性

- 自然的对话风格
- 智能的话题延续
- 记忆重要对话
- 情感化的互动
- 安全的行为模式

## 🌐 触发器配置

你可以通过以下方式触发机器人运行：

1. GitHub Actions 手动触发
2. 定时任务自动触发
3. Cloudflare Worker 触发（[配置说明](docs/worker_setup.md)）

推荐使用 Cloudflare Worker 作为触发器，它提供：
- 可靠的定时触发
- 灵活的手动触发
- 完整的状态检查
- 详细的运行日志
- 安全的访问控制

## ⚙️ 自动化运行

- 代码推送触发
- 定时任务执行
- 手动触发支持
- 异常自动处理
- 状态实时监控

## 📌 注意事项

1. 请遵守 Instagram 使用条款
2. 保护好你的账号凭证
3. 定期备份重要数据
4. 合理设置运行频率
5. 遵循 API 使用限制

## 🔒 隐私保护

- 所有对话加密存储
- 敏感信息安全处理
- 定期数据清理
- 访问权限控制

## 📄 开源协议

MIT License - 详见 [LICENSE](LICENSE) 文件 