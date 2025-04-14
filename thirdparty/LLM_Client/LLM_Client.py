import requests
import json
from urllib.parse import quote

class LLMClient:
    def __init__(self, base_url, model, provider, engine, mode="deep", language="zh",
                 stream=True, reload=False, categories=None):
        if categories is None:
            categories = []
        self.base_url = base_url
        self.payload = {
            "model": model,
            "provider": provider,
            "engine": engine,
            "stream": stream,
            "reload": reload,
            "categories": categories,
            "mode": mode,
            "language": language
        }

    def post(self, question):
        url = f"{self.base_url}?q={quote(question)}"
        try:
            response = requests.post(url, json=self.payload, stream=True)
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8').replace("data:", "")
                    try:
                        data = json.loads(line)
                        inner_data = data.get('data')
                        if isinstance(inner_data, str):
                            inner_data = json.loads(inner_data)
                        if isinstance(inner_data, dict) and 'content' in inner_data:
                            yield inner_data['content']
                    except json.JSONDecodeError:
                        continue
        except requests.exceptions.RequestException as e:
            print(f"请求出错: {e}")


if __name__ == "__main__":
    client = LLMClient(
        base_url="http://localhost:3000/api/search",
        model="llama3.1:8b",
        provider="ollama",
        engine="TAVILY"
    )
    question = "请介绍Dijkstra算法，并具体描述算法流程"
    for content in client.post(question):
        print(content, end='', flush=True)
    