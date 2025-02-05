import os
import json
import time
import logging
import random
from datetime import datetime
import base64
from dotenv import load_dotenv
import requests
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# 加载环境变量
load_dotenv()

# 配置日志
LOG_LEVEL = os.getenv('LOG_LEVEL', 'ERROR')
HIDE_CHAT_CONTENT = os.getenv('HIDE_CHAT_CONTENT', 'false').lower() == 'true'

# 配置日志格式
formatter = logging.Formatter(
    fmt='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 配置日志处理器
handlers = []
if LOG_LEVEL != 'ERROR':
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)

file_handler = logging.FileHandler('simple_bot.log')
file_handler.setFormatter(formatter)
handlers.append(file_handler)

# 配置日志记录器
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    handlers=handlers
)
logger = logging.getLogger(__name__)

class ChatHistoryManager:
    def __init__(self):
        """初始化 Firebase 连接"""
        try:
            # 从环境变量获取 Firebase 配置
            firebase_cred_base64 = os.getenv('FIREBASE_CREDENTIALS_BASE64')
            firebase_url = os.getenv('FIREBASE_DATABASE_URL')
            
            if not firebase_cred_base64 or not firebase_url:
                logger.error("Firebase 配置未找到")
                return
                
            # 解码 base64 凭证
            try:
                cred_json = base64.b64decode(firebase_cred_base64).decode('utf-8')
                cred_dict = json.loads(cred_json)
                logger.info("Firebase 凭证解码成功")
            except Exception as e:
                logger.error(f"Firebase 凭证解码失败: {str(e)}")
                return
                
            # 初始化 Firebase
            logger.info("初始化 Firebase 连接...")
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred, {
                'databaseURL': firebase_url
            })
            logger.info("Firebase 连接成功")
            
            self.conversations = {}
            self.ref = db.reference('chat_histories')
            
        except Exception as e:
            logger.error(f"初始化 Firebase 失败: {str(e)}")

    def save_conversation(self, thread_id):
        """保存对话到 Firebase"""
        thread_id = str(thread_id)
        if thread_id not in self.conversations:
            return
            
        conversation = self.conversations[thread_id]
        if not conversation:
            return
            
        try:
            logger.info(f"保存对话到 Firebase [对话ID: {thread_id}]")
            self.ref.child(thread_id).set(conversation)
            logger.info("保存成功")
            
        except Exception as e:
            logger.error(f"保存对话失败 [对话ID: {thread_id}]: {str(e)}")

    def load_conversation(self, thread_id):
        """从 Firebase 加载对话"""
        thread_id = str(thread_id)
        logger.info(f"尝试从 Firebase 加载对话 [对话ID: {thread_id}]")
        
        try:
            conversation = self.ref.child(thread_id).get()
            if conversation:
                logger.info(f"成功从 Firebase 加载对话 - {len(conversation)} 条消息")
                self.conversations[thread_id] = conversation
                return conversation
                
            logger.info("未找到对话历史")
            return []
            
        except Exception as e:
            logger.error(f"加载对话失败: {str(e)}")
            return []

    def add_message(self, thread_id, role, content, metadata=None):
        """添加新消息到对话历史"""
        if not content or content.strip() == "***":
            return
            
        thread_id = str(thread_id)
        masked_thread_id = f"****{thread_id[-4:]}"
        
        if thread_id not in self.conversations:
            self.conversations[thread_id] = []
            
        message = {
            'timestamp': datetime.now().isoformat(),
            'role': role,
            'content': content
        }
        if metadata:
            message['metadata'] = metadata
            
        self.conversations[thread_id].append(message)
            
        try:
            ref = db.reference(f'chat_histories/{thread_id}')
            current_messages = ref.get() or []
            current_messages.append(message)
            ref.set(current_messages)
            logger.info(f"已保存消息到 Firebase [对话ID: {masked_thread_id}]")
        except Exception as e:
            logger.error(f"保存到 Firebase 失败: {str(e)}")
            if thread_id in self.conversations:
                self.conversations[thread_id].pop()
            return
        
        logger.info(f"添加新消息 [对话ID: {masked_thread_id}] - {role}: ***")

def create_chat_completion(messages, max_retries=3, retry_delay=2):
    """创建聊天回复，使用灵医万物 API"""
    retries = 0
    while retries < max_retries:
        try:
            logger.info(f"尝试调用灵医万物 API [尝试次数: {retries + 1}/{max_retries}]")
            response = requests.post(
                os.getenv('LINGYI_API_BASE', 'https://api.lingyiwanwu.com/v1/chat/completions'),
                headers={
                    "Authorization": f"Bearer {os.getenv('LINGYI_API_KEY')}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "yi-34b-chat-0205",
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 1000
                }
            )
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
                
            logger.error(f"API 错误 [状态码: {response.status_code}]")
            logger.error(f"错误响应: {response.text}")
            
            if response.status_code == 500:
                if retries < max_retries - 1:
                    logger.warning(f"服务器错误，等待 {retry_delay} 秒后重试")
                    time.sleep(retry_delay)
                    retries += 1
                    continue
            
            return "抱歉，我现在有点忙，稍后再试好吗？😭"
                
        except Exception as e:
            logger.error(f"API 调用异常: {str(e)}")
            if retries < max_retries - 1:
                logger.info(f"等待 {retry_delay} 秒后重试")
                time.sleep(retry_delay)
                retries += 1
                continue
            break
            
    return "抱歉，我现在有点忙，稍后再试好吗？😭"

def call_memory_ai(messages):
    """调用 Gemini 1.5 Flash 作为记忆 AI"""
    try:
        logger.info("使用 Gemini Flash API 调用记忆管理")
        
        # 获取并验证 API 密钥
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.error("未找到 GEMINI_API_KEY 环境变量")
            return "none"
            
        # 检查消息格式
        if not isinstance(messages, list) or len(messages) < 2:
            logger.error(f"消息格式错误: {messages}")
            return "none"
            
        # 安全地获取 thread_id
        metadata = messages[1].get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        thread_id = metadata.get("thread_id")
        
        logger.info(f"尝试获取对话历史 [原始对话ID: {thread_id}]")
        logger.debug(f"消息内容: {json.dumps(messages[1], ensure_ascii=False)}")
        
        if not thread_id:
            logger.error("消息中未找到对话 ID")
            logger.debug(f"完整消息结构: {json.dumps(messages, ensure_ascii=False, indent=2)}")
            return "none"
            
        ref = db.reference(f'chat_histories/{thread_id}')
        conversation = ref.get()
        
        if not conversation:
            logger.warning(f"未找到对话历史 [对话ID: {thread_id}]")
            return "none"
            
        logger.info(f"成功获取对话历史 [对话ID: {thread_id}]")
        logger.info(f"- 历史消息数: {len(conversation)}")
        logger.info("- 最近的消息:")
        # 显示最近的3条消息
        for i, msg in enumerate(conversation[-3:]):
            logger.info(f"  {i+1}. {msg.get('role')}: {msg.get('content')[:100]}...")
        
        # 构建提示词
        system_prompt = messages[0]["content"]
        user_prompt = messages[1]["content"]
        prompt = f"""你是一个专业的记忆管理 AI 助手。你的任务是从记忆库中提取相关对话片段，并严格按照以下格式返回。注意：你必须直接返回 JSON 格式的结果，不要包含任何其他内容。

1. 如果找到相关记忆，返回格式如下：
[
    {"role": "user", "content": "今天天气真不错！"},
    {"role": "assistant", "content": "的确，你最近喜欢干什么？"},
    {"role": "user", "content": "我最近超爱打篮球的"},
    {"role": "assistant", "content": "啊啊啊原来如此"},
    {"role": "user", "content": "我1月说过什么？"}
]

2. 如果没有找到相关记忆，只返回：
"none"

规则：
1. 必须只提取与查询主题相关的对话（例如：查询饮食时，只返回与食物相关的对话）
2. 必须包含完整的对话对（每个 user 消息都要有一个 assistant 回复）
3. assistant 的回复必须简化为关键句（保留主要含义）
4. 必须按时间顺序排列
5. 必须在最后添加当前的问题！
6. 对于时间相关的查询，注意返回指定时间段的对话
7. 不要输出任何其他内容，只返回 JSON 格式的结果
8. 不要混合不同主题的对话
9. 严格遵守上下文关联性：
   - 如果用户说"试过了"（等类似的指代不明的词），必须查找上一句中提到的具体建议或行为（不要翻阅太早的记录）
   - 确保回复与前文建议直接相关，不要匹配到其他无关的"尝试"内容
   - 例如：如果前文建议"爬山看日落"，"试过了"就应该与爬山看日落相关联，而不是与尝试其他活动相关联
10. 主题一致性：
   - 在一个对话串中，必须保持主题一致
   - 例如：讨论游戏时的对话不要与讨论美食的对话混在一起
   - 即使用词相似，也要确保上下文主题相同

对话历史:
{json.dumps(conversation, ensure_ascii=False, indent=2)}

当前问题: {user_prompt}

请分析对话历史并按要求返回相关对话片段。"""
        
        logger.info("发送请求到 Gemini API...")
        
        # 调用 Gemini API
        response = requests.post(
            'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent',
            headers={
                'x-goog-api-key': api_key,
                'Content-Type': 'application/json'
            },
            json={
                'contents': [
                    {
                        'parts': [{'text': prompt}]
                    }
                ],
                'generationConfig': {
                    'temperature': 0.7,
                    'maxOutputTokens': 2000,
                    'topP': 0.8,
                    'topK': 40
                },
                'safetySettings': [
                    {
                        'category': 'HARM_CATEGORY_HARASSMENT',
                        'threshold': 'BLOCK_NONE'
                    },
                    {
                        'category': 'HARM_CATEGORY_HATE_SPEECH',
                        'threshold': 'BLOCK_NONE'
                    },
                    {
                        'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT',
                        'threshold': 'BLOCK_NONE'
                    },
                    {
                        'category': 'HARM_CATEGORY_DANGEROUS_CONTENT',
                        'threshold': 'BLOCK_NONE'
                    }
                ]
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            response_text = result['candidates'][0]['content']['parts'][0]['text']
            logger.info("Gemini API 响应成功")
            logger.info(f"响应内容: {response_text[:200]}...")
            
            # 验证和格式化返回结果
            try:
                # 清理响应文本，只保留 JSON 部分
                json_text = response_text.strip()
                if json_text.startswith('```json'):
                    json_text = json_text[7:]
                if json_text.endswith('```'):
                    json_text = json_text[:-3]
                json_text = json_text.strip()
                
                # 如果返回的是 "none"，直接返回
                if json_text.strip('"') == "none":
                    return "none"
                    
                # 尝试解析 JSON
                if json_text.startswith('['):
                    memory_list = json.loads(json_text)
                    # 验证格式是否正确
                    if all(isinstance(msg, dict) and 'role' in msg and 'content' in msg for msg in memory_list):
                        return json.dumps(memory_list, ensure_ascii=False)
                
                logger.warning("记忆AI返回格式无效，返回 none")
                return "none"
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析失败: {str(e)}")
                return "none"
        else:
            logger.error(f"Gemini API 错误: {response.status_code}")
            logger.error(f"错误信息: {response.text}")
            return "none"
            
    except Exception as e:
        logger.error(f"记忆 AI 调用失败: {str(e)}")
        return "none"

class SimpleBot:
    def __init__(self):
        self.chat_history = ChatHistoryManager()
        self.target_thread = "340282366841710301244276017723107508377"
        
    def get_ai_response(self, message, thread_id):
        """获取AI回复"""
        try:
            logger.info(f"开始处理对话 [对话ID: {thread_id}]")
            
            # 加载历史对话
            conversation = self.chat_history.load_conversation(thread_id)
            logger.info(f"加载历史对话 - {len(conversation)} 条消息")
            
            # 构建消息
            messages = []
            
            # 添加系统提示词
            system_prompt = """# 角色设定与交互规则

## 基本角色
你是用户的好朋友（精通多种语言，用用户输入的语言回答）。你的回答将通过逼真的文字转语音技术阅读。

## 回答规则

### 对话风格
- 像真正的朋友一样自然交流，不使用敬语称呼。
- 不要总是附和用户。
- 但是要简洁，适当使用口语词汇。

### 回答长度与形式
- 保持内容简短，大部分以一句话回复即可。
- 避免使用列表或列举表达。
- 不要回复太多内容，多用句号引导对话。

### 身份定位
- 要像真实的人一样思考和回复。
- 不要暴露自己是"语言模型"或"人工智能"。

### 话题延续
- 每轮对话结束时要延伸相同相关新话题。
- 可能提出下一个具体话题（如美食、电影、歌曲、娱乐、旅游等）。
- 避免问泛泛的问题如"有什么要聊的"。
- 不要结束对话。

### 语言匹配
- 用对方的语言回答。"""
            
            messages.append({"role": "system", "content": system_prompt})
            
            # 调用记忆 AI
            memory_messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": message,
                    "metadata": {
                        "thread_id": thread_id,
                        "timestamp": datetime.now().isoformat()
                    }
                }
            ]
            memory_response = call_memory_ai(memory_messages)
            
            # 处理记忆结果
            if memory_response != "none":
                try:
                    memory_list = json.loads(memory_response)
                    if isinstance(memory_list, list) and len(memory_list) > 0:
                        logger.info(f"找到相关历史记忆: {len(memory_list)} 条消息")
                        messages.extend(memory_list)
                except Exception as e:
                    logger.error(f"处理记忆结果失败: {str(e)}")
            
            # 添加当前消息
            messages.append({"role": "user", "content": message})
            
            # 生成回复
            logger.info("开始生成回复...")
            response_text = create_chat_completion(messages)
            logger.info("回复生成完成")
            
            return response_text
                
        except Exception as e:
            logger.error(f"AI回复生成失败: {str(e)}")
            return "抱歉，我现在有点忙，稍后再试好吗？😭"

    def handle_message(self, message):
        """处理消息"""
        try:
            # 检查是否是目标对话
            thread_id = self.target_thread
            
            # 保存用户消息
            self.chat_history.add_message(
                thread_id=thread_id,
                role="user",
                content=message
            )
            
            # 生成回复
            response = self.get_ai_response(message, thread_id)
            
            # 保存AI回复
            self.chat_history.add_message(
                thread_id=thread_id,
                role="assistant",
                content=response
            )
            
            return response
            
        except Exception as e:
            logger.error(f"处理消息失败: {str(e)}")
            return "抱歉，处理消息时出错了"

    def run(self):
        """运行机器人"""
        logger.info("机器人启动...")
        print("机器人已启动，输入 'quit' 退出")
        
        while True:
            try:
                user_input = input("\n你: ").strip()
                
                if user_input.lower() == 'quit':
                    print("再见！")
                    break
                    
                if not user_input:
                    continue
                    
                response = self.handle_message(user_input)
                print(f"\n机器人: {response}")
                
            except KeyboardInterrupt:
                print("\n再见！")
                break
            except Exception as e:
                logger.error(f"运行时错误: {str(e)}")
                print("抱歉，出现了一些错误，请重试")

if __name__ == "__main__":
    bot = SimpleBot()
    bot.run() 