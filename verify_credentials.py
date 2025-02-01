import os
import json
from dotenv import load_dotenv

def verify_credentials():
    load_dotenv()
    cred = os.getenv('FIREBASE_CREDENTIALS')
    if not cred:
        print("未找到凭证")
        return
        
    try:
        cred_dict = json.loads(cred)
        print("JSON 格式正确")
        print("包含的字段:", list(cred_dict.keys()))
    except json.JSONDecodeError as e:
        print("JSON 格式错误:", str(e))
        print("内容前100个字符:", cred[:100])

if __name__ == "__main__":
    verify_credentials() 