addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

// HTML 模板
const successTemplate = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram Bot Trigger</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: white;
            color: #1a1a1a;
        }
        .container {
            text-align: center;
            padding: 2rem;
        }
        .loader {
            width: 40px;
            height: 40px;
            border: 3px solid #eee;
            border-top: 3px solid #000;
            border-radius: 50%;
            margin: 20px auto;
            animation: spin 1s linear infinite;
            opacity: 1;
            transition: all 0.5s ease;
        }
        .checkmark {
            display: none;
            width: 40px;
            height: 40px;
            margin: 20px auto;
            border-radius: 50%;
            background: #00c853;
            position: relative;
            transform: scale(0);
            opacity: 0;
            transition: all 0.3s ease;
        }
        .checkmark:after {
            content: '';
            width: 20px;
            height: 10px;
            position: absolute;
            border: 2px solid white;
            border-top: none;
            border-right: none;
            background: transparent;
            top: 13px;
            left: 10px;
            transform: rotate(-45deg);
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .message {
            margin: 1rem 0;
            font-size: 1.1rem;
            font-weight: 500;
        }
        .redirect-text {
            font-size: 0.9rem;
            color: #666;
            margin-top: 0.5rem;
        }
        @keyframes success {
            from {
                transform: scale(0);
                opacity: 0;
            }
            to {
                transform: scale(1);
                opacity: 1;
            }
        }
    </style>
    <script>
        setTimeout(() => {
            document.querySelector('.loader').style.display = 'none';
            const checkmark = document.querySelector('.checkmark');
            checkmark.style.display = 'block';
            setTimeout(() => {
                checkmark.style.transform = 'scale(1)';
                checkmark.style.opacity = '1';
            }, 50);
            document.querySelector('.message').textContent = 'Bot Started';
        }, 2000);
        setTimeout(() => {
            window.location.href = 'instagram://app';
        }, 3000);
    </script>
    <meta http-equiv="refresh" content="3;url=instagram://app">
</head>
<body>
    <div class="container">
        <div class="loader"></div>
        <div class="checkmark"></div>
        <div class="message">Starting Bot...</div>
        <div class="redirect-text">Opening Instagram...</div>
    </div>
</body>
</html>
`

const errorTemplate = (message) => `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error - Instagram Bot Trigger</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: white;
            color: #1a1a1a;
        }
        .container {
            text-align: center;
            padding: 2rem;
            max-width: 80%;
        }
        .error-icon {
            width: 40px;
            height: 40px;
            margin: 20px auto;
            border-radius: 50%;
            background: #ff3b30;
            position: relative;
        }
        .error-icon:before,
        .error-icon:after {
            content: '';
            position: absolute;
            width: 24px;
            height: 2px;
            background: white;
            top: 19px;
            left: 8px;
        }
        .error-icon:before {
            transform: rotate(45deg);
        }
        .error-icon:after {
            transform: rotate(-45deg);
        }
        .error-message {
            margin: 1rem 0;
            font-size: 1rem;
            color: #666;
            white-space: pre-wrap;
            word-break: break-word;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="error-icon"></div>
        <div class="error-message">${message}</div>
    </div>
</body>
</html>
`

async function checkWorkflowStatus() {
  try {
    const response = await fetch(
      'https://api.github.com/repos/chiang881/instaBOT/actions/runs?per_page=10',
      {
        headers: {
          'Authorization': `Bearer ${GITHUB_TOKEN}`,
          'Accept': 'application/vnd.github.v3+json',
          'User-Agent': 'InstaBotTrigger/1.0'
        }
      }
    )
    
    if (!response.ok) {
      throw new Error('Failed to check workflow status')
    }
    
    const data = await response.json()
    // 检查最近的工作流运行状态
    const recentWorkflows = data.workflow_runs.filter(run => 
      run.name === 'Instagram Bot' && 
      (run.status === 'in_progress' || run.status === 'queued' || 
       (run.status === 'completed' && (Date.now() - new Date(run.updated_at).getTime()) < 60000))  // 1分钟内完成的
    )
    
    console.log('Recent workflows:', recentWorkflows.map(w => ({
      id: w.id,
      status: w.status,
      updated_at: w.updated_at
    })))
    
    return recentWorkflows.length > 0
  } catch (error) {
    console.error('Error checking workflow status:', error)
    return false
  }
}

async function handleRequest(request) {
  try {
    // 检查是否有正在运行或最近运行的工作流
    const isRunning = await checkWorkflowStatus()
    
    if (isRunning) {
      console.log('Workflow is already running or recently completed')
      return new Response(successTemplate, {
        headers: {
          'Content-Type': 'text/html;charset=UTF-8',
          'Cache-Control': 'no-store, no-cache, must-revalidate',
          'Pragma': 'no-cache'
        },
      })
    }

    console.log('No recent workflow found, triggering new one')
    
    // 如果没有运行中的工作流，触发新的工作流
    const response = await fetch('https://api.github.com/repos/chiang881/instaBOT/dispatches', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${GITHUB_TOKEN}`,
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
        'User-Agent': 'InstaBotTrigger/1.0'
      },
      body: JSON.stringify({
        event_type: 'trigger-bot'
      })
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`GitHub API responded with ${response.status}: ${errorText}`)
    }

    // 等待一小段时间确保工作流已经开始
    await new Promise(resolve => setTimeout(resolve, 2000))

    // 再次检查确保工作流已经开始
    const doubleCheck = await checkWorkflowStatus()
    if (!doubleCheck) {
      throw new Error('Failed to start workflow')
    }

    // 返回成功页面
    return new Response(successTemplate, {
      headers: {
        'Content-Type': 'text/html;charset=UTF-8',
        'Cache-Control': 'no-store, no-cache, must-revalidate',
        'Pragma': 'no-cache'
      },
    })
  } catch (error) {
    console.error('Error in handleRequest:', error)
    // 返回错误页面
    return new Response(errorTemplate(error.message), {
      status: 500,
      headers: {
        'Content-Type': 'text/html;charset=UTF-8',
        'Cache-Control': 'no-store, no-cache, must-revalidate',
        'Pragma': 'no-cache'
      },
    })
  }
}