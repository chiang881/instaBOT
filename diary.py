import os
import json
import logging
from datetime import datetime, timedelta
import pytz
import requests
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from dotenv import load_dotenv
from supabase import create_client, Client

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DiaryGenerator:
    def __init__(self):
        """初始化日记生成器"""
        # 从环境变量获取配置
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.firebase_cred_base64 = os.getenv('FIREBASE_CREDENTIALS_BASE64')
        self.firebase_url = os.getenv('FIREBASE_DATABASE_URL')
        
        # Supabase 配置
        self.supabase_url = os.getenv('SUPABASE_URL', 'https://vxkqsvwnejnoqiwxrzen.supabase.co')
        self.supabase_key = os.getenv('SUPABASE_KEY')
        self.supabase: Client = create_client(
            supabase_url=self.supabase_url,
            supabase_key=self.supabase_key
        )
        
        # 初始化数据库
        self._init_firebase()
        self._init_supabase()
        
        # 设置时区为北京时间
        self.timezone = pytz.timezone('Asia/Shanghai')
        
    def _init_firebase(self):
        """初始化 Firebase 连接"""
        try:
            if not self.firebase_cred_base64 or not self.firebase_url:
                raise ValueError("Firebase 配置未找到")
                
            # 解码 base64 凭证
            import base64
            cred_json = base64.b64decode(self.firebase_cred_base64).decode('utf-8')
            cred_dict = json.loads(cred_json)
            
            # 初始化 Firebase
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred, {
                'databaseURL': self.firebase_url
            })
            logger.info("Firebase 连接成功")
            
        except Exception as e:
            logger.error(f"初始化 Firebase 失败: {str(e)}")
            raise
            
    def _init_supabase(self):
        """初始化 Supabase 数据库"""
        try:
            # 检查表是否存在
            try:
                self.supabase.table('diaries').select('*').limit(1).execute()
                logger.info("Supabase diaries 表已存在")
            except Exception as e:
                logger.warning("Supabase diaries 表不存在，尝试创建")
                # 创建表的 SQL 语句
                create_table_sql = """
                create table if not exists diaries (
                    id bigint primary key generated always as identity,
                    date date not null,
                    content text not null,
                    timestamp timestamptz not null,
                    created_at timestamptz not null default now()
                );
                """
                
                # 使用 SQL API 创建表
                headers = {
                    'apikey': self.supabase_key,
                    'Authorization': f'Bearer {self.supabase_key}',
                    'Content-Type': 'application/json',
                    'Prefer': 'return=minimal'
                }
                
                response = requests.post(
                    f"{self.supabase_url}/rest/v1/sql",
                    headers=headers,
                    json={
                        "query": create_table_sql
                    }
                )
                
                if response.status_code in [200, 201]:
                    logger.info("成功创建 diaries 表")
                else:
                    logger.warning(f"创建表失败，状态码: {response.status_code}，将只保存到本地文件")
                    logger.debug(f"错误详情: {response.text}")
                
        except Exception as e:
            logger.error(f"初始化 Supabase 失败: {str(e)}")
            logger.info("将改为只保存到本地文件")
            
    def get_today_conversations(self):
        """获取今天的所有对话"""
        try:
            # 指定对话ID
            CONVERSATION_ID = "340282366841710301244276067357492128040"
            
            # 获取北京时间的今天的开始和结束时间
            now = datetime.now(self.timezone)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = now
            
            # 从 Firebase 获取特定对话
            ref = db.reference(f'chat_histories/{CONVERSATION_ID}')
            conversation_data = ref.get()
            
            if not conversation_data:
                logger.warning(f"未找到指定对话 [ID: {CONVERSATION_ID}]")
                return []
            
            # 合并所有子节点的消息
            all_messages = []
            
            # 处理数据，无论是字典还是列表
            if isinstance(conversation_data, dict):
                # 如果是字典（键值对）结构
                for node_id, messages in conversation_data.items():
                    if isinstance(messages, dict):
                        for msg_id, msg in messages.items():
                            if isinstance(msg, dict) and 'timestamp' in msg:
                                all_messages.append(msg)
            elif isinstance(conversation_data, list):
                # 如果是列表结构
                for msg in conversation_data:
                    if isinstance(msg, dict) and 'timestamp' in msg:
                        all_messages.append(msg)
            
            # 筛选今天的消息
            today_messages = []
            for msg in all_messages:
                try:
                    # 获取消息时间
                    msg_time = datetime.fromisoformat(msg['timestamp'])
                    msg_time = pytz.utc.localize(msg_time).astimezone(self.timezone)
                    
                    # 如果消息在今天的时间范围内
                    if today_start <= msg_time <= today_end:
                        # 提炼消息内容
                        refined_msg = {
                            'role': msg['role'],
                            'content': msg['content'],
                            'timestamp': msg['timestamp']
                        }
                        today_messages.append(refined_msg)
                except (KeyError, ValueError) as e:
                    logger.warning(f"跳过格式不正确的消息: {str(e)}")
                    continue
            
            # 按时间排序
            today_messages.sort(key=lambda x: x['timestamp'])
            logger.info(f"找到 {len(today_messages)} 条今天的消息")
            
            # 将对话整理成更易读的格式
            refined_conversations = []
            for msg in today_messages:
                time_str = datetime.fromisoformat(msg['timestamp']).astimezone(self.timezone).strftime('%H:%M')
                refined_msg = {
                    'time': time_str,
                    'role': msg['role'],
                    'content': msg['content']
                }
                refined_conversations.append(refined_msg)
            
            return refined_conversations
            
        except Exception as e:
            logger.error(f"获取今天对话失败: {str(e)}")
            return []
            
    def get_weather(self):
        """获取北京天气信息"""
        try:
            # 北京海淀区的经纬度
            params = {
                'latitude': 39.9789,
                'longitude': 116.3039,
                'current': 'temperature_2m,weather_code',
                'timezone': 'Asia/Shanghai'
            }
            
            response = requests.get('https://api.open-meteo.com/v1/forecast', params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                # 天气代码转换
                weather_codes = {
                    0: '晴朗', 1: '大部晴朗', 2: '多云', 3: '阴天',
                    45: '雾', 48: '雾凇',
                    51: '小毛毛雨', 53: '毛毛雨', 55: '大毛毛雨',
                    61: '小雨', 63: '中雨', 65: '大雨',
                    71: '小雪', 73: '中雪', 75: '大雪',
                    95: '雷暴', 96: '雷暴伴有小冰雹', 99: '雷暴伴有大冰雹'
                }
                
                weather_code = data['current']['weather_code']
                temperature = data['current']['temperature_2m']
                
                return {
                    'condition': weather_codes.get(weather_code, '未知天气'),
                    'temperature': temperature
                }
            else:
                raise Exception(f"天气API返回错误: {response.status_code}")
                
        except Exception as e:
            logger.error(f"获取天气信息失败: {str(e)}")
            return {
                'condition': '未知',
                'temperature': 20
            }
            
    def save_conversations_to_file(self, conversations):
        """将对话保存为临时文件"""
        try:
            # 创建临时目录
            os.makedirs('temp', exist_ok=True)
            file_path = os.path.join('temp', 'today_conversations.txt')
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("今日对话记录：\n\n")
                for msg in conversations:
                    # 根据角色设置说话人
                    speaker = "我" if msg['role'] == 'user' else "朋友"
                    f.write(f"[{msg['time']}] {speaker}：{msg['content']}\n")
                    
            logger.info(f"对话记录已保存到文件: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"保存对话记录到文件失败: {str(e)}")
            raise

    def _call_ai_model(self, prompt):
        """调用 AI 模型生成内容"""
        try:
            # 首先尝试调用 Gemini 1.5 Pro
            response = requests.post(
                'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent',
                headers={
                    'x-goog-api-key': self.api_key,
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
                    }
                }
            )
            
            if response.status_code == 200:
                logger.info("使用 Gemini 1.5 Pro 生成内容")
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                raise Exception(f"Gemini 1.5 Pro API 错误: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"Gemini 1.5 Pro 调用失败: {str(e)}，尝试使用备用模型")
            
            try:
                # 使用备用模型 Gemini 2.0 Flash
                response = requests.post(
                    'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-experimental:generateContent',
                    headers={
                        'x-goog-api-key': self.api_key,
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
                        }
                    }
                )
                
                if response.status_code == 200:
                    logger.info("使用 Gemini 2.0 Flash 生成内容")
                    return response.json()['candidates'][0]['content']['parts'][0]['text']
                else:
                    raise Exception(f"Gemini 2.0 Flash API 错误: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"备用模型调用也失败: {str(e)}")
                raise

    def generate_diary(self):
        """生成今天的日记"""
        try:
            # 获取今天的对话
            conversations = self.get_today_conversations()
            if not conversations:
                logger.warning("今天没有对话记录")
                return
                
            # 保存对话到文件
            conversation_file = self.save_conversations_to_file(conversations)
            
            # 获取天气信息
            weather = self.get_weather()
            
            # 读取对话文件内容
            with open(conversation_file, 'r', encoding='utf-8') as f:
                conversation_content = f.read()
            
            # 构建提示词
            current_time = datetime.now(self.timezone)
            prompt = f"""请根据以下信息，写一篇今天的日记：

时间：{current_time.strftime('%Y年%m月%d日')}
天气：{weather['condition']}，温度：{weather['temperature']}°C

{conversation_content}

要求：
1. 基本定位：将对话内容转化为一个人的真实生活记录，而不是对话记录
2. 内容结构：
   - 开头：简单的时间/天气/心情引入
   - 主体：当天的主要事件和感受，要自然地串联起来
   - 结尾：一个简短的思考或期待
   - 字数：控制在 100-300 字之间
3. 写作风格：
   - 使用第一人称叙述
   - 保持自然的口语化表达
   - 避免过于正式或书面的语言
   - 像真实的人在写私密日记一样表达
4. 情感表达：
   - 准确捕捉记忆中的情绪变化
   - 适当加入个人感受和思考
   - 表达要真实自然，不做作
5. 内容转化：
   - 将对话内容转化为个人经历描述
   - 把互动对话改写成自己的感悟
   - 保持事件的连贯性和逻辑性
   - 自然地引入新话题，而不是生硬的转折

请同时提供一个情感分析：
情感状态：[开心/难过/平静/兴奋/焦虑/其他]
情绪指数：[-10到10分，10分最积极]
主要情绪：[具体描述当天的主要情绪]
情绪变化：[如果有明显的情绪变化，请描述]
其他：[特别的感悟或期待]"""

            # 调用 AI 模型生成内容
            diary_content = self._call_ai_model(prompt)
            
            # 保存日记
            self.save_diary(diary_content)
            logger.info("日记生成并保存成功")
            
            # 清理临时文件
            try:
                os.remove(conversation_file)
                logger.info("临时文件已清理")
            except Exception as e:
                logger.warning(f"清理临时文件失败: {str(e)}")
                
        except Exception as e:
            logger.error(f"生成日记失败: {str(e)}")
            raise

    def save_diary(self, content):
        """保存日记到本地和 Supabase（如果可用）"""
        try:
            current_time = datetime.now(self.timezone)
            
            # 先保存到本地
            os.makedirs('diaries', exist_ok=True)
            file_path = os.path.join('diaries', f"{current_time.strftime('%Y-%m-%d')}.txt")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"日记已保存到本地: {file_path}")
            
            # 尝试保存到 Supabase
            try:
                diary_data = {
                    'date': current_time.strftime('%Y-%m-%d'),
                    'content': content,
                    'timestamp': current_time.isoformat(),
                    'created_at': current_time.isoformat()
                }
                
                response = self.supabase.table('diaries').insert(diary_data).execute()
                if hasattr(response, 'error') and response.error is not None:
                    raise Exception(f"Supabase 错误: {response.error}")
                logger.info("日记已保存到 Supabase")
            except Exception as e:
                logger.warning(f"保存到 Supabase 失败（将只保存在本地）: {str(e)}")
                
        except Exception as e:
            logger.error(f"保存日记失败: {str(e)}")
            raise

if __name__ == "__main__":
    try:
        generator = DiaryGenerator()
        generator.generate_diary()
    except Exception as e:
        logger.error(f"程序运行失败: {str(e)}")
        raise 