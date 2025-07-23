# KubeAgent

**KubeAgent** is An AI-Agent for automated Kubernetes troubleshooting, deployment, and management, based on LangChain and k8s related tools.


## Features

- Troubleshoot Kubernetes issues automatically
- Manage Kubernetes resources
- Search latest Kubernetes knowledge from internet
- Human in the Agent Loop, need approve when dangerous commands
- Chat memory
- Interactive console

## Usage

KubeAgent supports two interaction modes: command-line interface and web interface.

### Environment Configuration

Add environment variables to the `.env` file:
```sh
# DeepSeek API Key (default)
DEEPSEEK_API_KEY=your_deepseek_api_key
# Or use OpenAI API Key (optional)
# OPENAI_API_KEY=your_openai_api_key
KUBECONFIG=your_kubeconfig_path
```

### Running Methods

#### 1. Command Line Interface (Default)
```sh
python main.py
# Or explicitly specify
python main.py --mode console
```

#### 2. Web Interface
```sh
python main.py --mode web
# Custom port
python main.py --mode web --port 8080
```
Then access `http://localhost:5000` (or your specified port) in your browser

#### 3. Enable Both Interfaces
```sh
python main.py --mode both
```

### Command Line Interface Commands
```sh
kubeagent>: help
Available commands:
  - clear  :  Clear the chat history.
  - history:  Display the chat history.
  - help   :  Print help info.
  - exit   :  Exit the application.
  - *      :  Ask me everything about your kubernetes cluster(why my nginx pod not ready)
```

### Web Interface Features
- 🌐 Modern web chat interface
- 💬 Real-time conversation interaction
- **Streaming Output**: AI responses are displayed in real-time, including thinking process and tool execution steps
- 📱 Responsive design, supports mobile devices
- 🔄 Automatic chat history saving
- 🎨 Beautiful UI design
- Display AI's complete reasoning process (thinking, tool calls, results, etc.)

## Installation

1. Clone the repository:

   ```sh
   git clone https://github.com/molihua12345/kubeagent.git
   cd kubeagent
   ```

2. Install the dependencies:

   ```sh
   pip install -r requirements.txt
   ```

3. Copy the example environment file and configure it, set your `DEEPSEEK_API_KEY` and `KUBECONFIG`
   ```sh
   cp .env.example .env
   ```

   **Note**: The project uses DeepSeek API by default. If you want to use OpenAI API, you can pass a custom llm parameter when creating KubeAgent.

## License

This project is licensed under the terms of the Apache-2.0 license. See the [`LICENSE`](./LICENSE) file for details.
