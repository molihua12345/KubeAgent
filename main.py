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

def create_streaming_web_handler(kube_agent):
    def streaming_handler(console, message):
        try:
            # Track processed actions to avoid duplicates
            processed_actions = set()
            processed_steps = set()
            last_action_hash = None
            last_step_hash = None
            
            # Use the agent's stream method to get intermediate steps
            for chunk in kube_agent.stream({"input": message}):
                # Handle different types of chunks from LangChain streaming
                if "actions" in chunk:
                    # Agent is thinking/planning
                    action = chunk["actions"][0]
                    tool_name = action.tool
                    tool_input = action.tool_input
                    
                    # Create a more robust unique identifier
                    action_content = f"{tool_name}:{str(tool_input)}"
                    action_hash = hash(action_content)
                    
                    # Only yield if this is a genuinely new action
                    if action_hash != last_action_hash and action_hash not in processed_actions:
                        processed_actions.add(action_hash)
                        last_action_hash = action_hash
                        yield f"🤔 思考: 准备使用 {tool_name} 工具...\n"
                        yield f"📝 参数: {tool_input}\n\n"
                        
                elif "steps" in chunk:
                    # Tool execution result
                    step = chunk["steps"][0]
                    observation = step.observation
                    
                    # Create a more robust unique identifier for steps
                    step_content = f"{step.action.tool}:{str(step.action.tool_input)}:{str(observation)}"
                    step_hash = hash(step_content)
                    
                    # Only yield if this is a genuinely new step result
                    if step_hash != last_step_hash and step_hash not in processed_steps:
                        processed_steps.add(step_hash)
                        last_step_hash = step_hash
                        yield f"🔧 执行结果:\n{observation}\n\n"
                        
                elif "output" in chunk:
                    # Final answer
                    yield f"💡 最终回答:\n{chunk['output']}\n"
        except Exception as e:
            yield f"❌ 执行出错: {str(e)}\n"
    
    return streaming_handler

def main():
    parser = argparse.ArgumentParser(description='KubeAgent - AI Agent for Kubernetes')
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
        "KubeAgent",
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
        app.streaming_handler = create_streaming_web_handler(kube_agent)
    
    # Initialize CTH API with the agent's CTH agent instance
    try:
        from api import init_cth_api
        if hasattr(kube_agent, 'cth_agent'):
            init_cth_api(kube_agent.cth_agent)
            print("✅ CTH API initialized with KubeAgent's CTH instance")
    except ImportError:
        print("⚠️ CTH API not available")

    app.run(mode=args.mode)


if __name__ == "__main__":
    main()
