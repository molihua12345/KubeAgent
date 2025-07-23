import requests
import os
from langchain_core.tools import tool
from langchain.tools import BaseTool

@tool
def baidu_search_tool(query: str) -> str:
    """
    使用百度千帆AI搜索API进行联网搜索，返回搜索结果。

    参数:
    - query: 搜索关键词
    返回:
    - 搜索结果的字符串形式
    """
    # 从环境变量获取API密钥
    api_key = os.getenv('BAIDU_API_KEY')
    
    if not api_key:
        # 如果没有API密钥，提供备用的Kubernetes资源链接
        return f"""搜索关键词: {query}
                    由于未配置百度API密钥，无法进行在线搜索。
                    配置说明: 请在.env文件中设置BAIDU_API_KEY以启用在线搜索功能。"""
    
    url = 'https://qianfan.baidubce.com/v2/ai_search'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    messages = [
        {
            "content": query,
            "role": "user"
        }
    ]
    
    data = {
        "messages": messages,
        "search_source": "baidu_search_v2",
        "search_recency_filter": "month"  # 搜索最近一个月的内容
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            # 格式化搜索结果
            if 'result' in result:
                search_content = result['result']
                return f"搜索结果: {query}\n\n{search_content}\n\n"
            else:
                return str(result)
        else:
            # API请求失败时的备用方案
            return f"""API搜索暂时不可用 (状态码: {response.status_code}),错误信息: {response.text[:200]}..."""
            
    except requests.exceptions.Timeout:
        return f"""搜索请求超时"""
    except Exception as e:
        return f"""搜索过程中出现错误,错误信息: {str(e)}"""

class BaiduSearchTool(BaseTool):
    """兼容性包装器，保持与原有代码的兼容性"""
    name: str = "baidu_search"
    description: str = baidu_search_tool.description
    
    def _run(self, query: str) -> str:
        return baidu_search_tool.invoke({"query": query})
    
    async def _arun(self, query: str) -> str:
        return self._run(query)

def create_search_tool():
    return BaiduSearchTool()

if __name__ == "__main__":
    # 测试新的搜索工具
    print("=== 测试baidu_search_tool ===")
    print(f"工具名称: {baidu_search_tool.name}")
    print(f"工具描述: {baidu_search_tool.description}")
    print(f"工具参数: {baidu_search_tool.args}")
    print("\n=== 搜索测试 ===")
    result = baidu_search_tool.invoke({"query": "k8s latest version"})
    print(result)
    
    print("\n=== 测试兼容性包装器 ===")
    tool = create_search_tool()
    result2 = tool.run("kubernetes deployment")
    print(result2)
