# Worker 配置指南

本文档详细说明如何创建和配置用于触发机器人的 Cloudflare Worker。

## 创建 Worker

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com)
2. 进入 Workers & Pages
3. 创建新的 Worker
4. 使用以下代码模板：

```javascript
export default {
  async fetch(request, env) {
    try {
      // 获取设备信息
      const deviceInfo = {
        ip: request.headers.get('cf-connecting-ip'),
        userAgent: request.headers.get('user-agent'),
        platform: request.headers.get('sec-ch-ua-platform'),
        language: request.headers.get('accept-language'),
        timezone: new Date().toTimeString().split(' ')[1],
        timestamp: new Date().toISOString()
      }

      // 检查是否有正在运行的工作流
      const recentRuns = await checkWorkflowStatus(env.HUB_TOKEN)
      
      if (recentRuns) {
        return new Response("Workflow is already running", {
          status: 200,
          headers: { 'Content-Type': 'text/plain' }
        })
      }

      // 触发 GitHub Actions
      const response = await fetch(
        'https://api.github.com/repos/你的用户名/你的仓库名/dispatches',
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${env.HUB_TOKEN}`,
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
            'User-Agent': 'InstaBotTrigger/1.0'
          },
          body: JSON.stringify({
            event_type: 'trigger-bot',
            client_payload: { device_info: deviceInfo }
          })
        }
      )

      if (!response.ok) {
        throw new Error(`GitHub API responded with ${response.status}`)
      }

      return new Response("Bot triggered successfully", {
        status: 200,
        headers: { 'Content-Type': 'text/plain' }
      })
      
    } catch (error) {
      return new Response(`Error: ${error.message}`, {
        status: 500,
        headers: { 'Content-Type': 'text/plain' }
      })
    }
  }
}

async function checkWorkflowStatus(token) {
  const response = await fetch(
    'https://api.github.com/repos/你的用户名/你的仓库名/actions/runs?per_page=1',
    {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'InstaBotTrigger/1.0'
      }
    }
  )

  if (!response.ok) {
    throw new Error(`GitHub API responded with ${response.status}`)
  }

  const data = await response.json()
  if (data.workflow_runs.length > 0) {
    const latestRun = data.workflow_runs[0]
    const runTime = new Date(latestRun.created_at)
    const now = new Date()
    const timeDiff = (now - runTime) / 1000 / 60 // 转换为分钟

    return timeDiff < 30 && ['queued', 'in_progress'].includes(latestRun.status)
  }
  return false
}
```

## 配置说明

### 1. 环境变量设置

在 Worker 的设置页面中，添加以下环境变量：

- `HUB_TOKEN`: GitHub Personal Access Token
  - 需要 `repo` 和 `workflow` 权限
  - 建议设置合适的过期时间
  - 定期更新以保证安全性

### 2. 自定义域名（可选）

1. 在 Cloudflare DNS 中添加记录
2. 配置 Worker 的自定义域名
3. 确保 SSL/TLS 设置正确

### 3. 触发器配置

#### 定时触发
在 Worker 的 Triggers 页面配置 Cron 触发器：
```bash
*/30 * * * *  # 每30分钟触发一次
```

#### 手动触发
直接访问 Worker URL 即可触发，支持以下方式：
- 浏览器访问
- curl 命令调用
- 其他 HTTP 客户端

## 安全建议

### 1. 访问控制
- 设置请求频率限制
- 配置 IP 访问白名单
- 使用自定义域名时启用强制 HTTPS

### 2. Token 安全
- 定期轮换 GitHub Token
- 使用最小权限原则
- 监控异常访问情况

### 3. 错误处理
- 记录详细的错误日志
- 设置告警通知
- 定期检查运行状态

## 常见问题

### 1. Worker 无法触发
- 检查 Token 是否有效
- 确认仓库名称正确
- 验证 Actions 权限设置

### 2. 触发频率限制
- GitHub API 限制
- Workers 免费版限制
- 自定义域名限制

### 3. 安全问题
- Token 泄露处理
- 异常访问处理
- 权限调整方法 