#!/usr/bin/env python3
"""
KubeWizard Web Demo

这是一个演示脚本，展示如何启动KubeWizard的Web界面。
"""

from app.app import ConsoleApp, Handler
from agent.agent import KubeAgent
from utils.console import console
import argparse
import sys
import os

def create_streaming_web_handler(kube_agent):
    def streaming_handler(console, message):
        try:
            # Use the agent's stream method to get intermediate steps
            for chunk in kube_agent.stream({"input": message}):
                # Handle different types of chunks from LangChain streaming
                if "actions" in chunk:
                    # Agent is thinking/planning
                    action = chunk["actions"][0]
                    tool_name = action.tool
                    tool_input = action.tool_input
                    yield f"🤔 思考: 准备使用 {tool_name} 工具...\n"
                    yield f"📝 参数: {tool_input}\n\n"
                elif "steps" in chunk:
                    # Tool execution result
                    step = chunk["steps"][0]
                    observation = step.observation
                    yield f"🔧 执行结果:\n{observation}\n\n"
                elif "output" in chunk:
                    # Final answer
                    yield f"💡 最终回答:\n{chunk['output']}\n"
        except Exception as e:
            yield f"❌ 执行出错: {str(e)}\n"
    
    return streaming_handler

def main():
    parser = argparse.ArgumentParser(description='KubeWizard Web Demo')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the web server on')
    args = parser.parse_args()
    
    try:
        # Initialize the Kubernetes agent
        kube_agent = KubeAgent()
        
        # Create the console app with web interface
        app = ConsoleApp(
            name="KubeWizard",
            description="Kubernetes 智能助手 - 让容器管理更简单",
            web_port=args.port
        )
        
        # Set up streaming handler for web interface
        app.streaming_handler = create_streaming_web_handler(kube_agent)
        
        console.print("[bold green]🚀 启动 KubeWizard Web 界面...[/bold green]")
        console.print(f"[blue]📱 Web 界面地址: http://localhost:{args.port}[/blue]")
        console.print(f"[blue]📄 前端页面: file:///{os.path.abspath('frontend/index.html')}[/blue]")
        console.print("[yellow]💡 提示:[/yellow]")
        console.print("[yellow]  1. 后端服务已启动，提供 API 接口[/yellow]")
        console.print("[yellow]  2. 可以访问 Web 界面或打开独立前端页面[/yellow]")
        console.print("[yellow]  3. 按 Ctrl+C 停止服务[/yellow]")
        
        # Start in web mode
        app.run(mode='web')
        
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 再见![/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]❌ 启动失败: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    main()