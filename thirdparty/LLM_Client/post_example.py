import requests
import json
from urllib.parse import quote

# 定义 API 的 URL
base_url = "http://localhost:3000/api/search"

# 定义请求体
payload = {
    "model": "llama3.1:8b",
    "provider": "ollama",
    "engine": "TAVILY",
    "stream": True,
    "reload": False,
    "categories": [],
    "mode": "deep",
    "language": "zh"
}

# 定义要搜索的问题
question = "请介绍Dijkstra算法，并具体描述算法流程"

# 构建完整的 URL
url = f"{base_url}?q={quote(question)}"

try:
    # 发送流式请求
    response = requests.post(url, json=payload, stream=True)
    response.raise_for_status()

    # 处理流式响应，只提取 content 部分
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8').replace("data:", "")
            try:
                data = json.loads(line)
                inner_data = data.get('data')
                if isinstance(inner_data, str):
                    inner_data = json.loads(inner_data)
                if isinstance(inner_data, dict) and 'content' in inner_data:
                    print(inner_data['content'], end='', flush=True)
            except json.JSONDecodeError:
                continue

except requests.exceptions.RequestException as e:
    print(f"请求出错: {e}")