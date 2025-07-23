import readline
import time
import signal
import threading
import json
from typing import Callable, Dict, List, Optional, Any
from rich.console import Console
from rich.prompt import Prompt
from pyfiglet import figlet_format
from flask import Flask, request, jsonify, render_template_string, Response, send_from_directory
from flask_cors import CORS
import time

# Define the type for command handlers
CommandHandler = Callable[[Console, str], None]

class Handler:
    def __init__(self, name: str, handler: CommandHandler, description: str):
        self.name = name
        self.handler = handler
        self.description = description

class ConsoleApp:
    def __init__(
        self,
        name: str,
        description: str,
        command_handlers: Optional[List[Handler]] = None,
        default_handler: Optional[Handler] = None,
        web_port: int = 5000,
    ):
        """
        Initialize the console application.

        :param name: The application name.
        :param description: The application description.
        :param command_handlers: List of handlers for commands.
        :param default_handler: Default handler for unknown commands.
        :param web_port: Port for web server.
        """
        self.name = name
        self.description = description
        self.console = Console()
        self.command_handlers: Dict[str, Handler] = {handler.name: handler for handler in (command_handlers or [])}
        self.default_handler = default_handler or Handler("default", self.unknown_command_handler, "Default handler.")
        self.ctrl_c_count = 0
        self.web_port = web_port
        self.flask_app = None
        self.web_thread = None
        self.chat_history = []  # For web interface (deprecated, use agent memory instead)
        self.streaming_handler = None  # For streaming responses
        self.agent = None  # Reference to the agent for memory access

        # Register default handlers
        self.register_default_handlers()
        # Initialize Flask app
        self.init_flask_app()

    def init_flask_app(self):
        """
        Initialize Flask application for web interface.
        """
        self.flask_app = Flask(__name__)
        CORS(self.flask_app)       
        
        @self.flask_app.route('/')
        def serve_frontend():
            import os
            frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')
            return send_from_directory(frontend_dir, 'index.html')
        
        @self.flask_app.route('/api/chat', methods=['POST'])
        def api_chat():
            data = request.get_json()
            message = data.get('message', '')
            # Process the message using the default handler
            response = self.process_web_command(message)
            return jsonify({'response': response})
        
        @self.flask_app.route('/api/chat/stream', methods=['POST'])
        def api_chat_stream():
            print(f"[DEBUG] Received stream request from {request.remote_addr}")
            data = request.get_json()
            message = data.get('message', '')
            print(f"[DEBUG] Message: {message}")
            print(f"[DEBUG] Processing message with streaming handler")
            
            def generate_response():
                try:
                    print(f"[DEBUG] Starting response generation")
                    print(f"[DEBUG] Streaming handler available: {self.streaming_handler is not None}")
                    if self.streaming_handler:
                        # Use the streaming handler if available
                        print(f"[DEBUG] Using streaming handler")
                        chunk_count = 0
                        for chunk in self.streaming_handler(None, message):
                            chunk_count += 1
                            print(f"[DEBUG] Chunk {chunk_count}: {chunk[:50]}...")
                            # Send only the new chunk content, not accumulated
                            yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                            time.sleep(0.1)  # Small delay for better UX
                        
                        # Send final message to indicate completion
                        yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"
                    else:
                        # Fallback to original implementation
                        print(f"[DEBUG] Using fallback implementation")
                        full_response = self.process_web_command(message)
                        print(f"[DEBUG] Full response: {full_response[:100]}...")
                        
                        # Simulate streaming by sending chunks
                        words = full_response.split()
                        current_text = ""
                        print(f"[DEBUG] Split into {len(words)} words")
                        
                        for i, word in enumerate(words):
                            current_text += word + " "
                            # Send current progress as SSE
                            yield f"data: {json.dumps({'content': current_text.strip(), 'done': False})}\n\n"
                            time.sleep(0.05)  # Small delay to simulate streaming
                        
                        # Send final message
                        yield f"data: {json.dumps({'content': current_text.strip(), 'done': True})}\n\n"
                except Exception as e:
                    error_msg = f"执行出错: {str(e)}"
                    yield f"data: {json.dumps({'content': error_msg, 'done': True, 'error': True})}\n\n"
            return Response(generate_response(), mimetype='text/event-stream', headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': '*'
            })

        
        @self.flask_app.route('/api/history', methods=['GET'])
        def api_history():
            # Use agent memory if available, otherwise fallback to chat_history
            if self.agent and hasattr(self.agent, 'get_conversation_history'):
                history = self.agent.get_conversation_history()
                return jsonify({'history': history})
            return jsonify({'history': self.chat_history})
        
        @self.flask_app.route('/api/clear', methods=['POST'])
        def api_clear():
            # Clear agent memory if available, otherwise clear chat_history
            if self.agent and hasattr(self.agent, 'clear_conversation_history'):
                self.agent.clear_conversation_history()
            else:
                self.chat_history.clear()
            return jsonify({'status': 'success'})
        
        @self.flask_app.route('/api/health', methods=['GET'])
        def api_health():
            return jsonify({
                'status': 'healthy',
                'timestamp': time.time(),
                'version': '1.0.0'
            })

    def process_web_command(self, message: str) -> str:
        """
        Process command for web interface and return response as string.
        """
        try:
            # Execute the command
            command_parts = message.strip().lower().split()
            if command_parts:
                command = command_parts[0]
                handler = self.command_handlers.get(command, self.default_handler).handler
                
                # Create a simple console wrapper for web
                class WebConsole:
                    def __init__(self):
                        self.output = []
                    
                    def print(self, *args, **kwargs):
                        # Capture print output
                        import io
                        import sys
                        old_stdout = sys.stdout
                        sys.stdout = buffer = io.StringIO()
                        print(*args, **kwargs)
                        output = buffer.getvalue()
                        sys.stdout = old_stdout
                        self.output.append(output.strip())
                    
                    def clear(self):
                        self.output = []
                        return "屏幕已清除"
                
                web_console = WebConsole()
                result = handler(web_console, message)
                
                # Return the result from handler or captured output
                if result and isinstance(result, str):
                    return result
                elif web_console.output:
                    return '\n'.join(web_console.output)
                else:
                    return "命令已执行"
            else:
                return "请输入有效的命令"
            
        except Exception as e:
            return f"执行出错: {str(e)}"

    def register_default_handlers(self):
        """
        Register default command handlers.
        """
        self.command_handlers.setdefault("help", Handler("help", self.help_handler, "Print help info."))
        self.command_handlers.setdefault("exit", Handler("exit", self.exit_handler, "Exit the application."))
        self.command_handlers.setdefault("clear", Handler("clear", self.clear_handler, "Clear the screen."))

    def handle_interrupt(self, sig: int, frame: Any):
        """
        Handle Ctrl+C to provide a graceful exit.

        :param sig: Signal number.
        :param frame: Current stack frame.
        """
        self.ctrl_c_count += 1
        if self.ctrl_c_count == 1:
            self.console.print("Press Ctrl+C again to exit", style="red bold")
            time.sleep(0.5)
        elif self.ctrl_c_count >= 2:
            self.console.print("Goodbye!", style="cyan bold")
            exit(0)

    def print_welcome_message(self):
        """
        Print the welcome message and application title in ASCII art.
        """
        self.console.print(f"🎉 Welcome to {self.name}!")
        self.console.print(self.description, highlight=False)
        self.console.print("Type 'help' to see available commands.", highlight=False)
        self.console.print(figlet_format(self.name), style="cyan bold", highlight=False)

    def execute_command(self, command: str, raw: str):
        """
        Execute the given command.

        :param command: Command to execute.
        :param raw: Raw command input.
        """
        self.ctrl_c_count = 0
        handler = self.command_handlers.get(command, self.default_handler).handler
        handler(self.console, raw)

    def start_web_server(self):
        """
        Start the Flask web server in a separate thread.
        """
        def run_flask():
            self.flask_app.run(host='0.0.0.0', port=self.web_port, debug=False, use_reloader=False)
        
        self.web_thread = threading.Thread(target=run_flask, daemon=True)
        self.web_thread.start()
        self.console.print(f"🌐 Web interface started at http://localhost:{self.web_port}", style="green bold")

    def run(self, mode='console'):
        """
        Start the application.
        
        :param mode: 'console' for command line only, 'web' for web only, 'both' for both interfaces
        """
        signal.signal(signal.SIGINT, self.handle_interrupt)
        
        if mode in ['web', 'both']:
            self.start_web_server()
            
        if mode in ['console', 'both']:
            self.print_welcome_message()
            if mode == 'both':
                self.console.print(f"💡 You can also access the web interface at http://localhost:{self.web_port}", style="cyan")
            
            while True:
                try:
                    user_input = Prompt.ask(f"[magenta]{self.name.lower()}>[/magenta]")
                    if user_input:
                        readline.add_history(user_input)

                    command_parts = user_input.strip().lower().split()
                    if not command_parts:
                        self.console.print("")
                        continue
                    command = command_parts[0]
                    self.execute_command(command, user_input)
                except EOFError:
                    self.console.print("Exiting...", style="red bold")
                    break
        elif mode == 'web':
            self.console.print("🌐 Web-only mode. Access the interface at http://localhost:{}".format(self.web_port), style="green bold")
            self.console.print("Press Ctrl+C to stop the server.", style="yellow")
            try:
                # Keep the main thread alive
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.console.print("\nShutting down web server...", style="red bold")

    def help_handler(self, console: Console, args: Any):
        """
        Display a list of available commands.

        :param console: Console instance for printing.
        :param args: Additional arguments (unused).
        """
        console.print("Available commands:", style="blue bold")
        max_width = max(len(handler.name) for handler in self.command_handlers.values())
        for handler in self.command_handlers.values():
            console.print(f"  - {handler.name.ljust(max_width)}:  {handler.description}", style="blue")
        
        default_name = "*"
        console.print(f"  - {default_name.ljust(max_width)}:  {self.default_handler.description}", style="blue")

    def clear_handler(self, console: Console, args: Any):
        """
        Clear the screen.

        :param console: Console instance for printing.
        :param args: Additional arguments (unused).
        """
        console.clear()

    def exit_handler(self, console: Console, args: Any):
        """
        Exit the application.

        :param console: Console instance for printing.
        :param args: Additional arguments (unused).
        """
        console.print("Goodbye!", style="cyan bold")
        exit(0)

    def set_agent(self, agent):
        """
        Set the agent reference for accessing conversation history.
        
        :param agent: The agent instance to reference.
        """
        self.agent = agent

    def unknown_command_handler(self, console: Console, args: Any):
        """
        Handle unknown commands.

        :param console: Console instance for printing.
        :param args: Additional arguments (unused).
        """
        console.print("Unknown command. Type 'help' for a list of available commands.", style="red bold")

# Example usage
if __name__ == "__main__":
    app = ConsoleApp(
        "DemoApp",
        "This is a demo app.",
        command_handlers=[
            Handler("echo", lambda console, args: console.print(f"Echo: [blue]{args}[/blue]"), "Echo the input."),
        ],
    )
    app.run()
