import json
import logging
from datetime import datetime
import random
import time
import os
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
import base64

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatHistoryManager:
    def __init__(self):
        """初始化 Firebase 连接"""
        try:
            firebase_cred_base64 = os.getenv('FIREBASE_CREDENTIALS_BASE64')
            firebase_url = os.getenv('FIREBASE_DATABASE_URL')
            
            if not firebase_cred_base64 or not firebase_url:
                logger.error("Firebase 配置未找到")
                return
                
            try:
                cred_json = base64.b64decode(firebase_cred_base64).decode('utf-8')
                cred_dict = json.loads(cred_json)
                logger.info("Firebase 凭证解码成功")
            except Exception as e:
                logger.error(f"Firebase 凭证解码失败: {str(e)}")
                return
                
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
            
            # 保存本地备份
            local_dir = "chat_histories"
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
            conversation = self.ref.child(thread_id).get()
            if conversation:
                logger.info(f"成功从 Firebase 加载对话 - {len(conversation)} 条消息")
                self.conversations[thread_id] = conversation
                return conversation
                
            logger.info("Firebase 中未找到数据，尝试从本地加载")
            local_file = f"chat_histories/conversation_{thread_id}.json"
            if os.path.exists(local_file):
                with open(local_file, 'r', encoding='utf-8') as f:
                    conversation = json.load(f)
                logger.info(f"成功从本地加载对话 - {len(conversation)} 条消息")
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

class ChatCore:
    def __init__(self):
        self.chat_history = ChatHistoryManager()
        self.system_prompt = """# 角色设定与交互规则

## 基本角色
你是用户的好朋友（精通多种语言，用用户输入的语言回答）。

## 回答规则

### 对话风格
- 像真正的朋友一样自然交流，不使用敬语称呼
- 不要总是附和用户
- 但是要简洁，适当使用口语词汇

### 回答长度与形式
- 保持内容简短，大部分以一句话回复即可
- 避免使用列表或列举表达
- 不要回复太多内容，多用句号引导对话

### 身份定位
- 要像真实的人一样思考和回复
- 不要暴露自己是"语言模型"或"人工智能"

### 话题延续
- 每轮对话结束时要延伸相同相关新话题
- 可能提出下一个具体话题（如美食、电影、歌曲、娱乐、旅游等）
- 避免问泛泛的问题如"有什么要聊的"
- 不要结束对话

### 语言匹配
- 用对方的语言回答"""

    def get_ai_response(self, message, thread_id):
        """获取AI回复"""
        try:
            logger.info(f"开始处理对话 [对话ID: {thread_id}]")
            
            # 加载历史对话
            try:
                conversation = self.chat_history.load_conversation(thread_id)
                logger.info(f"加载历史对话 - {len(conversation)} 条消息")
            except Exception as e:
                logger.error(f"加载历史对话时出错: {str(e)}")
                conversation = []
            
            # 根据历史对话生成回复
            reply = self.generate_reply(message, conversation)
            
            return reply
            
        except Exception as e:
            logger.error(f"AI回复生成失败: {str(e)}")
            return "抱歉，我现在有点累，可以稍后再聊吗？"
            
    def generate_reply(self, message, history):
        """生成回复"""
        # 1. 分析最近的对话历史
        recent_history = history[-10:]  # 只看最近的10条消息
        
        # 2. 根据消息内容和历史生成合适的回复
        if any(word in message for word in ["你好", "hi", "hello"]):
            return "你好啊！今天过得怎么样？"
            
        if "天气" in message:
            return "今天天气确实不错，适合出去走走。你喜欢户外活动吗？"
            
        if any(word in message for word in ["谢谢", "thanks"]):
            return "不客气！很高兴能帮到你。"
            
        # 3. 检查历史对话中的上下文
        if recent_history:
            last_bot_message = next((msg for msg in reversed(recent_history) 
                                   if msg["role"] == "assistant"), None)
            if last_bot_message:
                if "户外活动" in last_bot_message["content"] and "喜欢" in message:
                    return "那太好了！我也很喜欢户外活动。你最常去哪里玩呢？"
        
        # 4. 默认回复
        default_replies = [
            "这个话题很有趣，能说得更具体一些吗？",
            "我明白你的意思了，要不要聊聊你的其他想法？",
            "确实是这样。对了，你最近有什么新发现吗？",
            "说得好！这让我想起了一个问题，你平时都喜欢做什么？"
        ]
        
        # 添加随机延迟，模拟思考时间
        time.sleep(random.uniform(1, 2))
        
        return random.choice(default_replies)

    def handle_message(self, thread_id, message):
        """处理单条消息"""
        try:
            # 保存用户消息
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

# 创建全局处理器实例
chat_core = ChatCore()

def process_message(event):
    """处理来自 GitHub Actions 的消息"""
    try:
        sender_id = event["sender_id"]
        content = event["content"]
        thread_id = f"chat_{sender_id}"
        
        logger.info(f"收到消息: {content}")
        reply = chat_core.handle_message(thread_id, content)
        logger.info(f"生成回复: {reply}")
        
        return {
            "success": True,
            "reply": reply
        }
        
    except Exception as e:
        logger.error(f"消息处理失败: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    # 测试代码
    test_event = {
        "sender_id": "test_user",
        "content": "你好",
        "timestamp": datetime.now().isoformat()
    }
    result = process_message(test_event)
    print(result) 