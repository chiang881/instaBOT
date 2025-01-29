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

1. Instagram 账号配置（在 bot.py 中）：
```python
INSTAGRAM_USERNAME = "your_username"
INSTAGRAM_PASSWORD = "your_password"
```

2. OpenAI 配置：
```python
openai.api_key = "your_api_key"
openai.api_base = "your_api_base"
```

## 自动化运行

项目通过以下方式自动运行：
1. 代码推送：每次推送到 main 分支时自动执行
2. 定时任务：每3小时自动执行一次
3. 手动触发：可以在 Actions 页面手动触发运行

## 注意事项

1. 建议使用私有仓库部署
2. 请遵守 Instagram 的使用条款和限制 