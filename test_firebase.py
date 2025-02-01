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

def test_firebase_connection():
    """测试 Firebase 连接和写入"""
    try:
        # 直接使用 JSON 文件
        cred_file = "instabot-181f3-firebase-adminsdk-fbsvc-4567ae4265.json"
        firebase_url = "https://instabot-181f3-default-rtdb.asia-southeast1.firebasedatabase.app"
        
        logger.info("初始化 Firebase 连接...")
        cred = credentials.Certificate(cred_file)
        firebase_admin.initialize_app(cred, {
            'databaseURL': firebase_url
        })
        logger.info("Firebase 连接成功")
        
        # 创建测试数据
        test_data = {
            "timestamp": "2025-01-30T13:32:53.967833",
            "role": "user",
            "content": "测试消息"
        }
        
        # 写入测试数据
        ref = db.reference('chat_histories')
        test_thread_id = "test_thread_001"
        
        logger.info(f"尝试写入测试数据到 thread_id: {test_thread_id}")
        ref.child(test_thread_id).set([test_data])
        
        # 读取测试数据验证
        logger.info("尝试读取测试数据")
        read_data = ref.child(test_thread_id).get()
        
        if read_data:
            logger.info(f"成功读取数据: {json.dumps(read_data, ensure_ascii=False)}")
            return True
        else:
            logger.error("未能读取数据")
            return False
            
    except Exception as e:
        logger.error(f"测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    # 运行测试
    success = test_firebase_connection()
    if success:
        logger.info("Firebase 测试成功！")
    else:
        logger.error("Firebase 测试失败！") 