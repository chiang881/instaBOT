import os
import json
import logging
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_and_write_conversation():
    """加载本地对话并写入 Firebase"""
    try:
        # 直接使用 JSON 文件
        cred_file = "instabot-181f3-firebase-adminsdk-fbsvc-4567ae4265.json"
        firebase_url = "https://instabot-181f3-default-rtdb.asia-southeast1.firebasedatabase.app"  # 更新为正确的区域 URL
        
        logger.info("初始化 Firebase 连接...")
        cred = credentials.Certificate(cred_file)
        firebase_admin.initialize_app(cred, {
            'databaseURL': firebase_url
        })
        logger.info("Firebase 连接成功")
        
        # 加载本地对话文件
        local_file = "downloaded_artifacts 22-29-31-785/artifact_2510800793/conversation_340282366841710301244276067357492128040.json"
        
        logger.info(f"加载本地对话文件: {local_file}")
        with open(local_file, 'r', encoding='utf-8') as f:
            conversation = json.load(f)
            
        # 写入 Firebase
        ref = db.reference('chat_histories')
        thread_id = "340282366841710301244276067357492128040"
        
        logger.info(f"写入对话到 Firebase [对话ID: {thread_id}]")
        ref.child(thread_id).set(conversation)
        
        # 验证写入
        logger.info("验证写入结果")
        read_data = ref.child(thread_id).get()
        
        if read_data:
            logger.info(f"成功写入和读取对话 - {len(read_data)} 条消息")
            return True
        else:
            logger.error("未能读取写入的数据")
            return False
            
    except Exception as e:
        logger.error(f"操作失败: {str(e)}")
        return False

if __name__ == "__main__":
    # 运行测试
    success = load_and_write_conversation()
    if success:
        logger.info("对话写入 Firebase 成功！")
    else:
        logger.error("对话写入 Firebase 失败！") 