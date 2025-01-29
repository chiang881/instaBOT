# Instagram Bot

一个基于 instagrapi 的 Instagram 自动化机器人，支持消息自动回复和模拟浏览行为。

## 功能特点

- 自动回复私信消息
- 模拟真实浏览行为
- 动态调整消息检查间隔
- 支持多种随机操作
- GitHub Actions 自动运行

## 运行环境

- Python 3.12+

## 配置说明

需要在 GitHub 仓库的 Settings -> Secrets and variables -> Actions 中添加以下 Secrets：

1. Instagram 账号配置：
- `INSTAGRAM_USERNAME`: Instagram 用户名
- `INSTAGRAM_PASSWORD`: Instagram 密码

2. OpenAI/Deepseek 配置：
- `OPENAI_API_KEY`: API密钥
- `OPENAI_API_BASE`: API基础URL（默认为 https://api.deepseek.com/v1）

## 自动化运行

项目通过以下方式自动运行：
1. 代码推送：每次推送到 main 分支时自动执行
2. 定时任务：每3小时自动执行一次
3. 手动触发：可以在 Actions 页面手动触发运行

## 注意事项

1. 建议使用私有仓库部署
2. 请遵守 Instagram 的使用条款和限制
3. 确保所有敏感信息都存储在 GitHub Secrets 中 