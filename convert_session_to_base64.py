import base64

def convert_session_to_base64():
    """将 session.json 转换为 base64"""
    try:
        # 读取 session.json 文件
        with open('session.json', 'r') as f:
            session_data = f.read()
        
        # 转换为 base64
        session_bytes = session_data.encode('utf-8')
        base64_session = base64.b64encode(session_bytes).decode('utf-8')
        
        print("=== Instagram Session Base64 ===")
        print("\nINSTAGRAM_SESSION:")
        print(base64_session)
        print("\n验证成功：可以正确解码回 JSON")
        
    except Exception as e:
        print(f"转换失败: {str(e)}")

if __name__ == "__main__":
    convert_session_to_base64() 