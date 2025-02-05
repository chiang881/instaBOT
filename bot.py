import os
from dotenv import load_dotenv
import json
import time
import logging
import random
import re
import imaplib
import email
from datetime import datetime
from instagrapi import Client
import openai
from instagrapi.mixins.challenge import ChallengeChoice
from instagrapi.exceptions import (
    BadPassword, ReloginAttemptExceeded, ChallengeRequired,
    SelectContactPointRecoveryForm, RecaptchaChallengeForm,
    FeedbackRequired, PleaseWaitFewMinutes, LoginRequired,
    ChallengeError, ChallengeSelfieCaptcha, ChallengeUnknownStep
)
import requests
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

# 加载 .env 文件
load_dotenv()

# 从环境变量获取日志级别和隐藏对话内容的设置
LOG_LEVEL = os.getenv('LOG_LEVEL', 'ERROR')  # 默认为 ERROR 级别
HIDE_CHAT_CONTENT = os.getenv('HIDE_CHAT_CONTENT', 'false').lower() == 'true'

# 自定义日志格式化器
class ChatContentFilter(logging.Formatter):
    def format(self, record):
        # 如果设置了隐藏对话内容且消息包含对话内容
        if HIDE_CHAT_CONTENT:
            # 检查是否包含对话内容的关键词
            keywords = ['content:', 'message:', 'user:', 'assistant:', '消息:']
            msg = record.getMessage()
            
            # 如果消息中包含这些关键词，替换具体内容为 ***
            for keyword in keywords:
                if keyword.lower() in msg.lower():
                    # 保留消息的开头部分（如时间戳和日志级别），但隐藏具体内容
                    record.msg = record.msg.split(keyword)[0] + keyword + ' ***'
                    break
                    
            # 特殊处理某些包含对话内容的日志
            if '历史消息:' in msg or '最近的消息:' in msg:
                record.msg = record.msg.split('\n')[0] + ' ***'
            elif 'AI回复:' in msg or '用户消息:' in msg:
                record.msg = record.msg.split(':')[0] + ': ***'
                
        return super().format(record)

# 配置日志
formatter = ChatContentFilter(
    fmt='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 配置日志处理器
handlers = []
if LOG_LEVEL != 'ERROR':
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)

# 文件处理器
file_handler = logging.FileHandler('bot.log')
file_handler.setFormatter(formatter)
handlers.append(file_handler)

# 配置日志记录器
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    handlers=handlers
)
logger = logging.getLogger(__name__)

# 从环境变量获取配置
INSTAGRAM_USERNAME = os.getenv('INSTAGRAM_USERNAME', '')
INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_API_BASE = os.getenv('OPENAI_API_BASE', 'https://api.deepseek.com/v1')
LINGYI_API_KEY = os.getenv('LINGYI_API_KEY', '')
LINGYI_API_BASE = os.getenv('LINGYI_API_BASE', 'https://api.lingyiwanwu.com/v1/chat/completions')
CHAT_HISTORY_KEY = os.getenv('CHAT_HISTORY_KEY', '')  # 用于加密聊天记录的密钥

# 配置OpenAI
openai.api_key = OPENAI_API_KEY
openai.api_base = OPENAI_API_BASE

# Gmail验证码邮箱配置（可选）
CHALLENGE_EMAIL = os.getenv('GMAIL_USERNAME', '')  # Gmail邮箱
CHALLENGE_PASSWORD = os.getenv('GMAIL_PASSWORD', '')  # Gmail密码

def get_code_from_email(username):
    """从Gmail获取验证码"""
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(CHALLENGE_EMAIL, CHALLENGE_PASSWORD)
        mail.select("inbox")
        result, data = mail.search(None, "(UNSEEN)")
        
        if result != "OK":
            logger.error(f"获取邮件失败: {result}")
            return False
            
        ids = data[0].split()
        for num in reversed(ids):
            mail.store(num, "+FLAGS", "\\Seen")  # 标记为已读
            result, data = mail.fetch(num, "(RFC822)")
            if result != "OK":
                continue
                
            email_body = email.message_from_bytes(data[0][1])
            if email_body.is_multipart():
                for part in email_body.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()
                        match = re.search(r">(\d{6})<", body)
                        if match:
                            return match.group(1)
            else:
                body = email_body.get_payload(decode=True).decode()
                match = re.search(r">(\d{6})<", body)
                if match:
                    return match.group(1)
                    
        return False
    except Exception as e:
        logger.error(f"处理邮件时出错: {str(e)}")
        return False

def challenge_code_handler(username, choice):
    """处理验证码"""
    if choice == ChallengeChoice.EMAIL:
        logger.info(f"正在从邮箱获取验证码...")
        return get_code_from_email(username)
    elif choice == ChallengeChoice.SMS:
        logger.info(f"需要短信验证码，请手动处理")
        return False
    return False

def change_password_handler(username):
    """生成新密码"""
    chars = list("abcdefghijklmnopqrstuvwxyz1234567890!&£@#")
    password = "".join(random.sample(chars, 12))  # 生成12位随机密码
    logger.info(f"为账号 {username} 生成新密码: {password}")
    return password

def create_chat_completion(messages, use_lingyi=True, max_retries=3, retry_delay=2):
    """创建聊天回复，只使用灵医万物 API"""
    retries = 0
    while retries < max_retries:
        try:
            logger.info(f"尝试调用灵医万物 API [尝试次数: {retries + 1}/{max_retries}]")
            response = requests.post(
                LINGYI_API_BASE,
                headers={
                    "Authorization": f"Bearer {LINGYI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "yi-34b-chat-0205",  # 指定模型
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 1000
                }
            )
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"], True
                
            # 记录详细的错误信息
            logger.error(f"API 错误 [状态码: {response.status_code}]")
            logger.error(f"错误响应: {response.text}")
            
            # 如果是 500 错误，等待后重试
            if response.status_code == 500:
                if retries < max_retries - 1:
                    logger.warning(f"服务器错误，等待 {retry_delay} 秒后重试")
                    time.sleep(retry_delay)
                    retries += 1
                    continue
            
            # 其他错误直接返回错误消息
            return "The server is too busy, I'm sorry I can't reply, you can try sending it to me again 😭", True
                
        except Exception as e:
            logger.error(f"API 调用异常: {str(e)}")
            if retries < max_retries - 1:
                logger.info(f"等待 {retry_delay} 秒后重试")
                time.sleep(retry_delay)
                retries += 1
                continue
            break
            
    # 所有重试都失败后返回错误消息
    return "The server is too busy, I'm sorry I can't reply, you can try sending it to me again 😭", True

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
        prompt = f"""请根据以下规则分析对话历史并回复：

{system_prompt}

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
            # 更新 Firebase
            self.ref.child(thread_id).set(conversation)
            logger.info("保存成功")
            
            # 同时保存本地备份
            local_dir = "downloaded_artifacts 22-29-31-785/artifact_2510800793"
            os.makedirs(local_dir, exist_ok=True)
            local_file = os.path.join(local_dir, f"conversation_{thread_id}.json")
            with open(local_file, 'w', encoding='utf-8') as f:
                json.dump(conversation, f, ensure_ascii=False, indent=2)
            logger.info(f"保存本地备份: {local_file}")
            
        except Exception as e:
            logger.error(f"保存对话失败 [对话ID: {thread_id}]: {str(e)}")

    def load_conversation(self, thread_id):
        """从 Firebase 加载对话"""
        thread_id = str(thread_id)
        logger.info(f"尝试从 Firebase 加载对话 [对话ID: {thread_id}]")
        
        try:
            # 从 Firebase 加载
            conversation = self.ref.child(thread_id).get()
            if conversation:
                logger.info(f"成功从 Firebase 加载对话 - {len(conversation)} 条消息")
                self.conversations[thread_id] = conversation
                return conversation
                
            # 如果 Firebase 没有数据，尝试从本地加载
            logger.info("Firebase 中未找到数据，尝试从本地加载")
            local_file = f"downloaded_artifacts 22-29-31-785/artifact_2510800793/conversation_{thread_id}.json"
            if os.path.exists(local_file):
                with open(local_file, 'r', encoding='utf-8') as f:
                    conversation = json.load(f)
                logger.info(f"成功从本地加载对话 - {len(conversation)} 条消息")
                # 同步到 Firebase
                self.ref.child(thread_id).set(conversation)
                logger.info("已同步本地数据到 Firebase")
                self.conversations[thread_id] = conversation
                return conversation
                
            logger.info("未找到对话历史")
            return []
            
        except Exception as e:
            logger.error(f"加载对话失败: {str(e)}")
            return []

    def add_message(self, thread_id, role, content, metadata=None):
        """添加新消息到对话历史"""
        # 如果内容为空或者全是 ***，则不保存
        if not content or content.strip() == "***":
            return
            
        thread_id = str(thread_id)
        masked_thread_id = f"****{thread_id[-4:]}"
        
        if thread_id not in self.conversations:
            self.conversations[thread_id] = []
            
        # 构建消息
        message = {
            'timestamp': datetime.now().isoformat(),
            'role': role,
            'content': content
        }
        if metadata:
            message['metadata'] = metadata
            
        # 先添加到内存中的对话列表
        self.conversations[thread_id].append(message)
        current_index = len(self.conversations[thread_id]) - 1
            
        # 保存到 Firebase，使用当前消息的索引
        try:
            ref = db.reference(f'chat_histories/{thread_id}')
            # 获取当前对话的所有消息
            current_messages = ref.get() or []
            # 添加新消息到列表末尾
            current_messages.append(message)
            # 更新整个对话历史
            ref.set(current_messages)
            logger.info(f"已保存消息到 Firebase [对话ID: {masked_thread_id}]")
        except Exception as e:
            logger.error(f"保存到 Firebase 失败: {str(e)}")
            # 如果保存失败，从内存中移除消息
            if thread_id in self.conversations:
                self.conversations[thread_id].pop()
            return
        
        # 最后记录日志
        logger.info(f"添加新消息 [对话ID: {masked_thread_id}] - {role}: ***")

class InstagramBot:
    def __init__(self, username, password):
        self.client = Client()
        self.username = username
        self.password = password
        self.last_check_time = None
        self.processed_messages = set()  # 用于跟踪已处理的消息
        self.relogin_attempt = 0
        self.max_relogin_attempts = 3
        self.use_lingyi = True
        
        # 对话上下文管理
        self.conversation_contexts = {}
        self.max_context_length = 20
        
        # 聊天历史管理
        self.chat_history = ChatHistoryManager()
        
        # 设置验证码处理器
        self.client.challenge_code_handler = challenge_code_handler
        self.client.change_password_handler = change_password_handler
        
        self.client.delay_range = [1, 3]
        self.daily_message_limit = 100
        self.message_count = 0
        self.setup_device()
        
    def setup_device(self):
        """设置设备信息和地区"""
        device = {
            "app_version": "269.0.0.18.75",
            "android_version": 26,
            "android_release": "8.0.0",
            "dpi": "480dpi",
            "resolution": "1080x1920",
            "manufacturer": "OnePlus",
            "device": "6T",
            "model": "ONEPLUS A6010",
            "cpu": "qcom",
            "version_code": "301484483"
        }
        self.client.set_device(device)
        self.client.set_user_agent()
        
        # 设置地区信息
        self.client.set_country("US")
        self.client.set_locale("en_US")
        self.client.set_timezone_offset(-7 * 60 * 60)  # Los Angeles UTC-7
        
    def handle_exception(self, e):
        """处理各种异常"""
        if isinstance(e, BadPassword):
            logger.error(f"密码错误: {str(e)}")
            if self.relogin_attempt >= self.max_relogin_attempts:
                raise ReloginAttemptExceeded("超过最大重试次数")
            self.relogin_attempt += 1
            return self.login()
            
        elif isinstance(e, LoginRequired):
            logger.warning("需要重新登录")
            return self.relogin()
            
        elif isinstance(e, ChallengeRequired):
            logger.warning("需要处理验证挑战")
            try:
                # 尝试自动处理验证挑战
                challenge = self.client.last_json
                if challenge.get("step_name") == "select_verify_method":
                    # 优先选择邮箱验证
                    choices = challenge.get("step_data", {}).get("choice")
                    if choices:
                        if ChallengeChoice.EMAIL in choices:
                            self.client.challenge_resolve(challenge, ChallengeChoice.EMAIL)
                        elif ChallengeChoice.SMS in choices:
                            self.client.challenge_resolve(challenge, ChallengeChoice.SMS)
                        else:
                            raise ChallengeUnknownStep("未知的验证方式")
                elif challenge.get("step_name") == "verify_code":
                    self.client.challenge_resolve(challenge)
                elif challenge.get("step_name") == "verify_email":
                    self.client.challenge_resolve(challenge)
                elif challenge.get("step_name") == "change_password":
                    self.client.challenge_resolve(challenge)
                    # 更新密码
                    new_password = change_password_handler(self.username)
                    self.password = new_password
                    logger.info("密码已更新")
                else:
                    raise ChallengeUnknownStep(f"未知的验证步骤: {challenge.get('step_name')}")
                    
                logger.info("验证挑战处理成功")
                return True
                
            except (ChallengeRequired, SelectContactPointRecoveryForm, RecaptchaChallengeForm, ChallengeError, ChallengeSelfieCaptcha, ChallengeUnknownStep) as e:
                logger.error(f"无法自动处理验证挑战: {str(e)}")
                raise
                
        elif isinstance(e, FeedbackRequired):
            message = self.client.last_json.get("feedback_message", "")
            if "This action was blocked" in message:
                logger.warning("操作被暂时阻止，等待12小时")
                time.sleep(12 * 3600)
            elif "Your account has been temporarily blocked" in message:
                logger.error("账号被临时封禁")
                raise
            elif "challenge_required" in message:
                logger.warning("需要处理验证挑战")
                return self.handle_exception(ChallengeRequired())
                
        elif isinstance(e, PleaseWaitFewMinutes):
            wait_time = random.uniform(300, 600)  # 等待5-10分钟
            logger.warning(f"需要等待一段时间，将等待{wait_time/60:.1f}分钟")
            time.sleep(wait_time)
            
        else:
            logger.error(f"未处理的异常: {str(e)}")
            raise

    def load_session(self):
        """加载或创建会话"""
        try:
            session = self.client.load_settings("session.json")
            if session:
                self.client.set_settings(session)
                try:
                    self.client.get_timeline_feed()
                    logger.info("成功使用现有会话登录")
                    return True
                except (LoginRequired, ChallengeRequired) as e:
                    logger.info("会话已过期或需要验证，需要重新登录")
                    old_session = self.client.get_settings()
                    self.client.set_settings({})
                    self.client.set_uuids(old_session["uuids"])
                    if isinstance(e, ChallengeRequired):
                        self.handle_exception(e)
        except Exception as e:
            logger.info(f"加载会话失败: {str(e)}")
        
        return False

    def relogin(self):
        """重新登录"""
        try:
            # 首先尝试从环境变量获取 session
            session_base64 = os.getenv('INSTAGRAM_SESSION')
            if session_base64:
                try:
                    logger.info("从环境变量获取 session")
                    # 解码 base64 session
                    session_json = base64.b64decode(session_base64).decode('utf-8')
                    # 保存到临时文件
                    with open('session.json', 'w') as f:
                        f.write(session_json)
                    # 加载 session
                    if self.client.load_settings('session.json'):
                        try:
                            self.client.get_timeline_feed()
                            logger.info("使用环境变量中的 session 登录成功")
                            return True
                        except Exception as e:
                            logger.warning(f"使用环境变量中的 session 登录失败: {str(e)}")
                except Exception as e:
                    logger.error(f"处理环境变量中的 session 失败: {str(e)}")
            
            # 如果环境变量中的 session 无效，尝试使用用户名密码登录
            logger.info("尝试使用用户名密码登录")
            self.client.login(self.username, self.password)
            self.client.dump_settings("session.json")
            logger.info("重新登录成功")
            return True
            
        except Exception as e:
            logger.error(f"重新登录失败: {str(e)}")
            self.handle_exception(e)
            return False

    def login(self):
        """登录 Instagram"""
        try:
            # 尝试从 Firebase 加载会话
            ref = db.reference('instagram_session')
            session_data = ref.get()
            
            if session_data:
                logger.info("从 Firebase 加载会话数据")
                # 将会话数据写入临时文件
                with open('session.json', 'w') as f:
                    json.dump(session_data, f)
                    
                try:
                    # 使用会话文件登录
                    self.client.load_settings('session.json')
                    self.client.login(self.username, self.password)
                    logger.info("使用已保存的会话登录成功")
                    return True
                except Exception as e:
                    logger.error(f"使用已保存会话登录失败: {str(e)}")
                    # 继续尝试使用用户名密码登录
            
            # 使用用户名密码登录
            logger.info("尝试使用用户名密码登录")
            self.client.login(self.username, self.password)
            
            try:
                # 保存新会话到 Firebase
                self.client.dump_settings('session.json')
                with open('session.json', 'r') as f:
                    session_data = json.load(f)
                ref.set(session_data)
                logger.info("登录成功并保存新会话到 Firebase")
            except Exception as e:
                logger.error(f"保存会话到 Firebase 失败: {str(e)}")
                # 即使保存失败也继续运行
            
            return True
            
        except Exception as e:
            logger.error(f"登录失败: {str(e)}")
            try:
                # 即使登录失败也尝试保存会话
                self.client.dump_settings('session.json')
                with open('session.json', 'r') as f:
                    session_data = json.load(f)
                ref.set(session_data)
                logger.info("已保存会话到 Firebase")
            except Exception as save_error:
                logger.error(f"保存会话失败: {str(save_error)}")
            
            return False

    def summarize_context(self, context):
        """使用AI总结对话上下文"""
        try:
            messages = [
                {"role": "system", "content": "请将以下对话总结为20字以内的要点，保留关键信息。"},
                {"role": "user", "content": context}
            ]
            summary, _ = create_chat_completion(messages, self.use_lingyi)
            logger.info(f"对话上下文总结: ***")
            return summary
        except Exception as e:
            logger.error(f"总结上下文失败: {str(e)}")
            return ""

    def get_ai_response(self, message, thread_id):
        """获取AI回复"""
        try:
            # 先记录原始对话ID
            logger.info(f"开始处理对话 [原始对话ID: {thread_id}]")
            
            # 隐藏敏感信息的线程ID
            masked_thread_id = f"****{str(thread_id)[-4:]}"
            logger.info(f"处理对话 [掩码对话ID: {masked_thread_id}]")
            
            # 加载历史对话
            try:
                conversation = self.chat_history.load_conversation(thread_id)
                logger.info(f"加载历史对话 [对话ID: {thread_id}] - {len(conversation)} 条消息")
            except Exception as e:
                logger.error(f"加载历史对话时出错: {str(e)}")
                conversation = []
            
            # 构建记忆提取提示词
            memory_messages = [
                {
                    "role": "system",
                    "content": """你是一个专业的记忆管理 AI 助手。你的任务是从记忆库中提取相关对话片段，并严格按照以下格式返回。注意：你必须直接返回 JSON 格式的结果，不要包含任何其他内容。

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
   - 即使用词相似，也要确保上下文主题相同"""
                },
                {
                    "role": "user",
                    "content": f"历史对话：{json.dumps(conversation, ensure_ascii=False)}\n\n当前问题：{message}",
                    "metadata": {
                        "thread_id": thread_id,
                        "timestamp": datetime.now().isoformat()
                    }
                }
            ]
            
            logger.info(f"开始调用记忆AI [对话ID: {thread_id}]")
            logger.info(f"当前问题: {message}")
            memory_response = call_memory_ai(memory_messages)
            logger.info(f"记忆AI返回结果: ***")
            
            # 处理记忆结果
            try:
                if memory_response != "none":
                    memory_list = json.loads(memory_response)
                    if isinstance(memory_list, list) and len(memory_list) > 0:
                        logger.info(f"找到相关历史记忆: {len(memory_list)} 条消息")
                        messages = memory_list + [{"role": "user", "content": message}]
                    else:
                        logger.info("记忆格式无效，忽略历史记忆")
                        messages = [{"role": "user", "content": message}]
                else:
                    logger.info("没有找到相关历史记忆")
                    messages = [{"role": "user", "content": message}]
            except Exception as e:
                logger.error(f"处理记忆结果时出错: {str(e)}")
                messages = [{"role": "user", "content": message}]
            
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
            
            messages.insert(0, {"role": "system", "content": system_prompt})
            
            # 生成回复
            try:
                time.sleep(random.uniform(1, 3))
                logger.info(f"开始调用对话AI生成回复")
                response_text, switch_to_lingyi = create_chat_completion(messages, self.use_lingyi)
                if switch_to_lingyi:
                    self.use_lingyi = True
                logger.info(f"对话AI回复: ***")
                
                return response_text
            except Exception as e:
                logger.error(f"生成回复时出错: {str(e)}")
                return "The server is too busy, I'm sorry I can't reply, you can try sending it to me again 😭"
                
        except Exception as e:
            logger.error(f"AI回复生成失败: {str(e)}")
            return "The server is too busy, I'm sorry I can't reply, you can try sending it to me again 😭"

    def load_conversation_history(self, thread_id):
        """根据对话ID加载特定的历史对话"""
        try:
            thread_id = str(thread_id)
            local_dir = "downloaded_artifacts 22-29-31-785/artifact_2510800793"
            filename = f"conversation_{thread_id}.json"
            filepath = os.path.join(local_dir, filename)
            
            if os.path.exists(filepath):
                logger.info(f"找到对话历史文件 [对话ID: {thread_id}]")
                with open(filepath, 'r', encoding='utf-8') as f:
                    conversation = json.load(f)
                
                # 将对话加载到chat_history中
                self.chat_history.conversations[thread_id] = conversation
                logger.info(f"成功加载对话历史 [对话ID: {thread_id}]")
                logger.info(f"- 消息数量: {len(conversation)}")
                logger.info("- 最近的消息:")
                # 显示最近的3条消息
                for i, msg in enumerate(conversation[-3:]):
                    logger.info(f"  {i+1}. {msg.get('role')}: {msg.get('content')[:100]}...")
                return True
            else:
                logger.info(f"未找到对话历史文件 [对话ID: {thread_id}]")
                return False
        except Exception as e:
            logger.error(f"加载对话历史失败 [对话ID: {thread_id}]: {str(e)}")
            return False

    def process_thread(self, thread):
        """处理单个对话线程"""
        try:
            if self.message_count >= self.daily_message_limit:
                logger.warning("已达到每日消息限制")
                return
                
            thread_id = str(thread.id)
            
            # 在处理消息前加载该对话的历史记录
            self.load_conversation_history(thread_id)
            
            # 获取完整的对话内容（最近1条消息）
            full_thread = self.client.direct_thread(thread_id, amount=1)
            if not full_thread.messages:
                return
                
            # 获取最新消息
            message = full_thread.messages[0]
            
            # 检查消息是否已经回复过
            if message.id in self.processed_messages:
                return
            
            # 处理消息
            if message.item_type == 'text' and message.text:
                self.handle_text_messages([message], thread_id)
            elif message.item_type in ['media', 'clip', 'voice_media', 'animated_media', 'reel_share']:
                self.handle_media_message(message, thread_id)
                    
        except Exception as e:
            logger.error(f"处理消息时出错: {str(e)}")
            self.handle_exception(e)

    def handle_text_messages(self, messages, thread_id):
        """处理多条文本消息"""
        try:
            thread_id = str(thread_id)
            # 只有多条消息时才使用编号格式
            if len(messages) > 1:
                combined_message = "\n".join([f"{i+1}. {msg.text}" for i, msg in enumerate(messages)])
                logger.info(f"合并处理 {len(messages)} 条消息 [对话ID: {thread_id}]")
            else:
                combined_message = messages[0].text
                logger.info(f"处理单条消息 [对话ID: {thread_id}]")
            
            # 先保存用户消息
            for message in messages:
                self.chat_history.add_message(
                    thread_id=thread_id,
                    role='user',
                    content=message.text,
                    metadata={
                        'message_id': message.id,
                        'thread_id': thread_id,
                        'timestamp': datetime.now().isoformat()
                    }
                )
                logger.info(f"已保存用户消息 [对话ID: {thread_id}]")
            
            # 生成AI回复
            logger.debug(f"开始生成AI回复 [对话ID: {thread_id}]")
            ai_response = self.get_ai_response(combined_message, thread_id)
            logger.debug(f"AI回复内容: {ai_response}")
            time.sleep(random.uniform(2, 5))
            
            # 使用direct_answer发送回复
            try:
                self.client.direct_answer(thread_id, ai_response)
                logger.info(f"回复成功 [对话ID: {thread_id}] - 消息已发送")
                
                # 保存AI回复
                self.chat_history.add_message(
                    thread_id=thread_id,
                    role='assistant',
                    content=ai_response,
                    metadata={
                        'thread_id': thread_id,
                        'timestamp': datetime.now().isoformat()
                    }
                )
                logger.info(f"已保存AI回复 [对话ID: {thread_id}]")
                
                # 标记所有消息为已处理
                for message in messages:
                    self.processed_messages.add(message.id)
                self.message_count += 1
                
            except Exception as e:
                logger.error(f"发送回复失败: {str(e)}")
        except Exception as e:
            logger.error(f"处理文本消息时出错: {str(e)}")
            self.handle_exception(e)
                
    def handle_media_message(self, message, thread_id):
        """处理媒体消息"""
        try:
            thread_id = str(thread_id)  # 确保thread_id是字符串
            logger.info(f"收到媒体消息 [对话ID: {thread_id}]: {message.item_type}")
            # 记录媒体消息
            self.chat_history.add_message(thread_id, 'user', f"[{message.item_type}]")
            
            response = "Unsupported file type 😭"
            try:
                self.client.direct_answer(thread_id, response)
                logger.info(f"已回复不支持的文件类型提示 [对话ID: {thread_id}]")
                # 记录AI回复
                self.chat_history.add_message(thread_id, 'assistant', response)
                self.processed_messages.add(message.id)
                self.message_count += 1
            except Exception as e:
                logger.error(f"回复媒体消息失败: {str(e)}")
                self.handle_exception(e)
        except Exception as e:
            logger.error(f"处理媒体消息时出错: {str(e)}")
            self.handle_exception(e)

    def handle_messages(self):
        """处理消息，动态调整检查间隔
        Returns:
            bool: 如果需要继续运行返回True，如果需要退出返回False
        """
        logger.info("开始监听消息...")
        
        last_message_time = time.time()  # 上次收到消息的时间
        first_check = True  # 标记是否是首次检查
        is_processing = False  # 标记是否正在处理消息
        consecutive_errors = 0  # 连续错误计数
        
        while True:
            current_time = time.time()
            time_since_last_message = current_time - last_message_time  # 距离上次消息的时间
            
            # 检查是否需要退出（2分钟无消息或连续错误过多）
            if not first_check and time_since_last_message > 120:
                logger.info("超过2分钟没有新消息，退出监听")
                return False
            
            if consecutive_errors >= 3:
                logger.info("连续错误过多，退出监听")
                return False
            
            if not is_processing:
                logger.info(f"正在检查新消息... 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            has_new_message = False
            try:
                # 检查未读消息
                unread_threads = self.client.direct_threads(amount=20, selected_filter="unread")
                if unread_threads:
                    logger.info(f"发现 {len(unread_threads)} 个未读对话")
                    is_processing = True
                    for thread in unread_threads:
                        self.process_thread(thread)
                    has_new_message = True
                    last_message_time = time.time()  # 更新最后活动时间
                    is_processing = False
                    consecutive_errors = 0  # 重置错误计数
                
                # 检查待处理消息
                pending_threads = self.client.direct_pending_inbox(20)
                if pending_threads:
                    logger.info(f"发现 {len(pending_threads)} 个待处理对话")
                    is_processing = True
                    for thread in pending_threads:
                        self.process_thread(thread)
                    has_new_message = True
                    last_message_time = time.time()  # 更新最后活动时间
                    is_processing = False
                    consecutive_errors = 0  # 重置错误计数
                
                if not has_new_message and not is_processing:
                    logger.info("没有新消息")
                    if first_check:  # 首次检查无消息
                        logger.info("首次检查无消息，等待30秒后重试")
                        time.sleep(30)
                        first_check = False  # 标记首次检查已完成
                    else:
                        # 根据无消息时长设置检查间隔
                        if time_since_last_message <= 60:  # 1分钟内
                            check_interval = random.uniform(3, 6)
                            logger.info(f"1分钟内，设置检查间隔: {check_interval:.1f}秒")
                        else:  # 1-2分钟
                            check_interval = random.uniform(15, 20)
                            logger.info(f"超过1分钟无消息，设置检查间隔: {check_interval:.1f}秒")
                        
                        time.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"消息处理出错: {str(e)}")
                self.handle_exception(e)
                is_processing = False  # 确保处理状态被重置
                consecutive_errors += 1  # 增加错误计数
                time.sleep(5)  # 出错后等待一段时间再继续
            
            if has_new_message:
                first_check = False  # 收到消息后标记首次检查完成
        
        return True

    def browse_feed(self, duration=None):
        """浏览公共随机帖子
        Args:
            duration (int, optional): 浏览时长（秒）。如果不指定，将随机浏览50-70秒
        """
        try:
            if duration is None:
                duration = random.randint(50, 70)  # 约1分钟
            
            start_time = time.time()
            logger.info(f"开始浏览公共帖子，计划持续 {duration} 秒")
            
            # 热门标签列表
            hashtags = [
                "photography", "art", "nature", "travel", "food",
                "fashion", "beauty", "fitness", "music", "dance",
                "pets", "cats", "dogs", "sunset", "architecture",
                "design", "style", "portrait", "landscape", "street"
            ]
            
            # 随机选择2个标签
            selected_hashtags = random.sample(hashtags, 2)
            logger.info(f"本次选择的标签: {selected_hashtags}")
            
            # 标签页类型
            tab_types = ["top", "recent"]
            
            try:
                for hashtag in selected_hashtags:
                    if time.time() - start_time >= duration:
                        break
                        
                    # 随机选择一个标签页类型
                    tab_key = random.choice(tab_types)
                    logger.info(f"浏览标签 #{hashtag} 下的{tab_key}帖子")
                    
                    try:
                        # 模拟点击标签的延迟
                        time.sleep(random.uniform(1, 3))
                        medias = self.client.hashtag_medias_v1(hashtag, amount=5, tab_key=tab_key)
                        
                        if medias:
                            logger.info(f"获取到 {len(medias)} 个帖子")
                            for media in medias:
                                if time.time() - start_time >= duration:
                                    break
                                
                                try:
                                    # 模拟滚动到帖子的延迟
                                    time.sleep(random.uniform(0.5, 1.5))
                                    
                                    # 获取帖子详细信息
                                    media_info = self.client.media_info_v1(media.pk)
                                    if media_info:
                                        logger.info(f"浏览帖子: {media_info.pk} - 类型: {media_info.media_type}")
                                        
                                        # 模拟查看帖子详情的随机时间
                                        view_time = random.uniform(2, 6)
                                        logger.info(f"查看帖子 {view_time:.1f} 秒")
                                        time.sleep(view_time)
                                        
                                except Exception as e:
                                    logger.warning(f"获取帖子详情失败: {str(e)}")
                                
                        else:
                            logger.warning(f"标签 #{hashtag} 下未获取到帖子")
                    except Exception as e:
                        logger.warning(f"获取标签 #{hashtag} 的帖子失败: {str(e)}")
                        continue
                
            except Exception as e:
                logger.warning(f"浏览帖子时出错: {str(e)}")
            
            actual_duration = int(time.time() - start_time)
            logger.info(f"浏览公共帖子完成，实际持续了 {actual_duration} 秒")
            
        except Exception as e:
            logger.error(f"浏览帖子时出错: {str(e)}")
            self.handle_exception(e)

    def random_action(self):
        """执行随机动作"""
        # 定义可能的操作和它们的概率
        actions = [
            (self.browse_feed, 0.3),  # 30%概率浏览帖子
            (lambda: time.sleep(random.uniform(30, 60)), 0.7)  # 70%概率休息
        ]
        
        action, _ = random.choices(
            population=[a[0] for a in actions],
            weights=[a[1] for a in actions],
            k=1
        )[0]
        
        action()

    def run(self):
        """主运行循环"""
        try:
            self.login()
            message_count = 0
            
            while True:
                # 登录后，70%概率直接回复消息，30%概率先浏览再回复
                if random.random() < 0.7:
                    logger.info("直接处理消息")
                    if not self.handle_messages():  # 检查handle_messages的返回值
                        logger.info("消息处理完成，退出程序")
                        break  # 如果handle_messages返回False，退出循环
                else:
                    logger.info("先浏览帖子再处理消息")
                    self.browse_feed()  # 约1分钟
                    if not self.handle_messages():  # 检查handle_messages的返回值
                        logger.info("消息处理完成，退出程序")
                        break  # 如果handle_messages返回False，退出循环
                
                message_count += 1
                
                # 每处理3-5条消息后执行随机动作
                if message_count >= random.randint(3, 5):
                    message_count = 0
                    self.random_action()
                
                # 保存所有对话历史
                self.chat_history.save_all_conversations()
                
                # 随机延迟10-30秒
                time.sleep(random.uniform(10, 30))
                
        except Exception as e:
            logger.error(f"运行时出错: {str(e)}")
            self.handle_exception(e)
            # 确保在错误发生时也保存对话历史
            self.chat_history.save_all_conversations()

    def download_chat_history(self):
        """下载并解密历史对话"""
        try:
            from download_artifacts import ArtifactsDownloader
            
            # 从环境变量获取token和key
            github_token = os.getenv('GITHUB_TOKEN', '')
            encryption_key = os.getenv('CHAT_HISTORY_KEY', '')
            
            if not github_token or not encryption_key:
                logger.warning("未找到GitHub token或加密密钥，尝试加载本地历史对话")
                self.load_local_history()
                return
                
            logger.info("尝试从 GitHub Artifacts 下载历史对话...")
            logger.info("初始化 ArtifactsDownloader")
            downloader = ArtifactsDownloader(github_token, encryption_key)
            
            # 获取最近的运行记录
            logger.info("获取最近的工作流运行记录")
            runs = downloader.get_workflow_runs()
            if not runs:
                logger.warning("没有找到工作流运行记录，尝试加载本地历史对话")
                self.load_local_history()
                return
            
            latest_run = runs[0]
            logger.info(f"找到最近的运行记录 ID: {latest_run['id']}")
            
            # 获取最近一次运行的artifacts
            logger.info(f"获取运行 ID {latest_run['id']} 的 artifacts")
            artifacts = downloader.get_artifacts(latest_run["id"])
            
            if not artifacts:
                logger.warning("没有找到artifacts，尝试加载本地历史对话")
                self.load_local_history()
                return
            
            logger.info(f"找到 {len(artifacts)} 个 artifacts")
            
            # 下载、解压并解密artifacts
            for artifact in artifacts:
                logger.info(f"检查 artifact: {artifact['name']}")
                if "chat-history" in artifact["name"]:
                    logger.info(f"找到聊天历史 artifact，ID: {artifact['id']}")
                    logger.info("开始下载和解压")
                    artifact_dir = downloader.download_and_extract(artifact["id"], "downloaded_chat_history")
                    if artifact_dir:
                        logger.info(f"成功从 GitHub Artifacts 下载历史对话到: {artifact_dir}")
                        # 加载下载的对话到内存
                        self.load_downloaded_conversations(artifact_dir)
                        return
                    else:
                        logger.error("下载或解压失败")
                        
            logger.warning("未找到聊天历史相关的 artifacts，尝试加载本地历史对话")
            self.load_local_history()
            
        except Exception as e:
            logger.error(f"下载历史对话失败: {str(e)}，尝试加载本地历史对话")
            self.load_local_history()

    def load_local_history(self):
        """加载本地历史对话文件"""
        try:
            # 修改为相对路径
            local_dir = "downloaded_artifacts 22-29-31-785/artifact_2510800793"
            logger.info(f"开始从本地加载历史对话，目录: {local_dir}")
            
            if os.path.exists(local_dir):
                logger.info(f"找到本地历史对话目录: {local_dir}")
                loaded_files = 0
                for filename in os.listdir(local_dir):
                    if filename.startswith("conversation_") and filename.endswith(".json"):
                        try:
                            filepath = os.path.join(local_dir, filename)
                            logger.info(f"正在加载本地对话文件: {filename}")
                            
                            with open(filepath, 'r', encoding='utf-8') as f:
                                conversation = json.load(f)
                            
                            # 从文件名中提取thread_id
                            thread_id = filename.replace('conversation_', '').replace('.json', '')
                            
                            # 将对话加载到chat_history中
                            self.chat_history.conversations[thread_id] = conversation
                            loaded_files += 1
                            
                            logger.info(f"成功从本地加载对话历史 [对话ID: {thread_id}]")
                            logger.info(f"- 消息数量: {len(conversation)}")
                            logger.info("- 最近的消息:")
                            # 显示最近的3条消息
                            for i, msg in enumerate(conversation[-3:]):
                                logger.info(f"  {i+1}. {msg.get('role')}: {msg.get('content')[:100]}...")
                            
                        except Exception as e:
                            logger.error(f"加载本地对话文件失败 {filename}: {str(e)}")
                
                if loaded_files > 0:
                    logger.info(f"共成功从本地加载 {loaded_files} 个对话文件")
                else:
                    logger.warning("本地目录中没有找到有效的对话文件")
            else:
                logger.warning(f"本地历史对话目录不存在: {local_dir}")
        except Exception as e:
            logger.error(f"加载本地历史对话文件失败: {str(e)}")

    def load_downloaded_conversations(self, artifact_dir):
        """加载下载的对话到内存"""
        logger.info(f"开始加载下载的对话文件，目录: {artifact_dir}")
        try:
            loaded_files = 0
            for filename in os.listdir(artifact_dir):
                if filename.endswith('.enc'):
                    try:
                        thread_id = filename.replace('conversation_', '').replace('.enc', '')
                        filepath = os.path.join(artifact_dir, filename)
                        logger.info(f"加载对话文件: {filename}")
                        
                        with open(filepath, 'rb') as f:
                            encrypted_data = f.read()
                        data = self.cipher_suite.decrypt(encrypted_data)
                        conversation = json.loads(data.decode('utf-8'))
                        
                        self.chat_history.conversations[thread_id] = conversation
                        loaded_files += 1
                        logger.info(f"成功加载对话 [对话ID: {thread_id}] - {len(conversation)} 条消息")
                        
                    except Exception as e:
                        logger.error(f"加载对话文件失败 {filename}: {str(e)}")
            
            logger.info(f"共加载了 {loaded_files} 个对话文件")
            
        except Exception as e:
            logger.error(f"加载下载的对话失败: {str(e)}")

    def handle_message(self, thread_id, message):
        """处理单条消息"""
        try:
            # 先保存用户消息
            self.chat_history.add_message(
                thread_id=thread_id,
                role="user",
                content=message,
                metadata={"thread_id": thread_id}
            )
            
            # 生成回复
            response = self.get_ai_response(message, thread_id)
            
            # 保存助手回复
            self.chat_history.add_message(
                thread_id=thread_id,
                role="assistant",
                content=response
            )
            
            return response
            
        except Exception as e:
            logger.error(f"处理消息失败: {str(e)}")
            return "抱歉，处理消息时出错了"

if __name__ == "__main__":
    bot = InstagramBot(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
    
    try:
        bot.run()
    except Exception as e:
        logger.error(f"机器人崩溃: {str(e)}")