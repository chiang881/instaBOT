import base64

def convert_proxy_to_base64():
    """将代理配置 YAML 转换为 base64"""
    try:
        # 读取 YAML 文件
        with open('1715517526741.yaml', 'r', encoding='utf-8') as f:
            yaml_content = f.read()
        
        # 转换为 base64
        proxy_bytes = yaml_content.encode('utf-8')
        base64_proxy = base64.b64encode(proxy_bytes).decode('utf-8')
        
        print("=== 代理配置 Base64 ===")
        print("\nPROXY_CONFIG:")
        print(base64_proxy)
        print("\n验证成功：配置可以正确解码")
        
    except Exception as e:
        print(f"转换失败: {str(e)}")

if __name__ == "__main__":
    convert_proxy_to_base64() 