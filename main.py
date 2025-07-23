import dotenv
import argparse

from agent import KubeAgent
from app import ConsoleApp, Handler


def create_web_handler(kube_agent):
    """Create a web-compatible handler that returns string responses."""
    def web_handler(console, args):
        try:
            result = kube_agent.invoke(args)
            # Extract the output from the agent result
            if isinstance(result, dict) and 'output' in result:
                return result['output']
            elif hasattr(result, 'get') and result.get('output'):
                return result.get('output')
            else:
                return str(result)
        except Exception as e:
            return f"处理出错: {str(e)}"
    return web_handler


def main():
    parser = argparse.ArgumentParser(description='KubeWizard - AI Agent for Kubernetes')
    parser.add_argument('--mode', choices=['console', 'web', 'both'], default='console',
                       help='运行模式: console(命令行), web(Web界面), both(两者都启用)')
    parser.add_argument('--port', type=int, default=5000,
                       help='Web服务器端口 (默认: 5000)')
    
    args = parser.parse_args()
    
    dotenv.load_dotenv()

    kube_agent = KubeAgent()

    # Create handlers
    def clear_handler(console, args):
        console.clear()
        kube_agent.memory.clear()  # Also clear agent memory
        return "聊天历史已清除"
    
    def history_handler(console, args):
        messages = kube_agent.get_chat_messages()
        if hasattr(console, 'print'):
            console.print(messages)
        return str(messages)

    app = ConsoleApp(
        "KubeWizard",
        "这是一个用于Kubernetes的AI代理，可以进行故障排除、部署和管理。",
        command_handlers=[
            Handler(
                "clear",
                clear_handler,
                "Clear the chat history.",
            ),
            Handler(
                "history",
                history_handler,
                "Display the chat history.",
            ),
        ],
        default_handler=Handler(
            "default",
            create_web_handler(kube_agent),
            "Ask me everything about your kubernetes cluster(why my nginx pod not ready)",
        ),
        web_port=args.port,
    )
    
    # Set streaming handler for web interface
    if args.mode in ['web', 'both']:
        from web_demo import create_streaming_web_handler
        app.streaming_handler = create_streaming_web_handler(kube_agent)

    app.run(mode=args.mode)


if __name__ == "__main__":
    main()
