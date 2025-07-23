# Kubewizard

**Kubewizard** is An AI-Agent for automated Kubernetes troubleshooting, deployment, and management, based on LangChain and k8s related tools.


## Features

- Troubleshoot Kubernetes issues automatically
- Manage Kubernetes resources
- Search latest Kubernetes knowledge from internet
- Human in the Agent Loop, need approve when dangerous commands
- Chat memory
- Interactive console

## Usage

KubeWizard 支持两种交互方式：命令行界面和Web界面。

### 环境配置

添加环境变量到 `.env` 文件:
```sh
# DeepSeek API Key (默认使用)
DEEPSEEK_API_KEY=your_deepseek_api_key
# 或者使用 OpenAI API Key (可选)
# OPENAI_API_KEY=your_openai_api_key
KUBECONFIG=your_kubeconfig_path
```

### 运行方式

#### 1. 命令行界面 (默认)
```sh
python main.py
# 或者明确指定
python main.py --mode console
```

#### 2. Web界面
```sh
python main.py --mode web
# 自定义端口
python main.py --mode web --port 8080
```
然后在浏览器中访问 `http://localhost:5000` (或您指定的端口)

#### 3. 同时启用两种界面
```sh
python main.py --mode both
```

#### 4. 快速启动Web演示
```sh
python web_demo.py
```

### 命令行界面命令
```sh
kubewizard>: help
Available commands:
  - clear  :  Clear the chat history.
  - history:  Display the chat history.
  - help   :  Print help info.
  - exit   :  Exit the application.
  - *      :  Ask me everything about your kubernetes cluster(why my nginx pod not ready)
```

### Web界面特性
- 🌐 现代化的Web聊天界面
- 💬 实时对话交互
- **流式输出**: AI回答会实时显示，包括思考过程和工具执行步骤
- 📱 响应式设计，支持移动设备
- 🔄 自动保存聊天历史
- 🎨 美观的UI设计
- 显示AI的完整推理过程（思考、工具调用、结果等）

## Installation

1. Clone the repository:

   ```sh
   git clone https://github.com/yourusername/kubewizard.git
   cd kubewizard
   ```

2. Install the dependencies:

   ```sh
   pip install -r requirements.txt
   ```

3. Copy the example environment file and configure it, set your `DEEPSEEK_API_KEY` and `KUBECONFIG`
   ```sh
   cp .env.example .env
   ```

   **注意**: 项目默认使用 DeepSeek API。如果你想使用 OpenAI API，可以在创建 KubeAgent 时传入自定义的 llm 参数。

## License

This project is licensed under the terms of the Apache-2.0 license. See the [`LICENSE`](./LICENSE) file for details.
