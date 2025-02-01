import base64
import json

def convert_credentials_to_base64():
    """将 Firebase 凭证和数据库 URL 转换为 base64"""
    try:
        # 读取 JSON 文件
        with open('instabot-181f3-firebase-adminsdk-fbsvc-4567ae4265.json', 'r') as f:
            cred_json = f.read()
        
        # 转换凭证为 base64
        cred_bytes = cred_json.encode('utf-8')
        base64_cred = base64.b64encode(cred_bytes).decode('utf-8')
        
        # 数据库 URL
        database_url = "https://instabot-181f3-default-rtdb.asia-southeast1.firebasedatabase.app"
        
        print("=== GitHub Secrets 配置 ===")
        print("\nFIREBASE_CREDENTIALS_BASE64:")
        print(base64_cred)
        print("\nFIREBASE_DATABASE_URL:")
        print(database_url)
        
        # 验证凭证转换是否正确
        decoded = base64.b64decode(base64_cred).decode('utf-8')
        json.loads(decoded)  # 确保可以解析回 JSON
        print("\n验证成功：凭证可以正确解码回 JSON")
        
    except Exception as e:
        print(f"转换失败: {str(e)}")

if __name__ == "__main__":
    convert_credentials_to_base64() 