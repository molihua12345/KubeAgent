# KubeAgent

**KubeAgent** is An AI-Agent for automated Kubernetes troubleshooting, deployment, and management, based on LangChain and k8s related tools. Now enhanced with **CTH (Causal-Temporal Hypergraph)** framework for advanced fault propagation analysis and intelligent diagnosis.

## 🚀 New: CTH Framework Integration

KubeAgent now includes a cutting-edge **Causal-Temporal Hypergraph (CTH)** framework that revolutionizes cloud-native system fault diagnosis:

- **🔗 Multi-entity Correlation**: Uses hyperedges to represent concurrent events involving multiple entities
- **⏱️ Temporal Analysis**: Tracks fault propagation over time with precise causality
- **🧠 LLM-Powered Diagnosis**: Combines structured graph analysis with large language model reasoning
- **🔧 Automated Remediation**: Generates executable repair commands and detailed incident reports
- **📊 Scope Quantification**: Measures fault impact and propagation velocity

### CTH Key Features

1. **Hypergraph Construction**: Automatically builds CTH from traces, metrics, and logs
2. **Propagation Path Analysis**: Identifies fault propagation routes with probability scoring
3. **Resilience Pattern Detection**: Recognizes retry, timeout, circuit breaker, and bulkhead patterns
4. **Interactive Diagnosis**: ReAct-style agent for dynamic fault investigation
5. **Smart Remediation**: Context-aware repair plan generation

## Features

### Core Features
- **Natural Language Interface**: Interact with your Kubernetes cluster using plain English
- **Intelligent Troubleshooting**: AI-powered diagnosis of common Kubernetes issues
- **Automated Problem Resolution**: Suggests and can execute fixes for detected problems
- **Multi-modal Interface**: Available as both command-line tool and web interface
- **Real-time Monitoring**: Continuous monitoring and alerting capabilities
- **Safe Operations**: Built-in approval mechanisms for destructive operations
- **Knowledge Integration**: Search latest Kubernetes knowledge from internet
- **Chat Memory**: Maintains conversation context for better assistance
- **Interactive Console**: User-friendly command-line interface

### CTH Framework Features
- **🔍 Advanced Fault Analysis**: Multi-dimensional fault propagation analysis using hypergraph theory
- **📈 Observability Integration**: Seamlessly processes traces, metrics, and logs from multiple sources
- **🎯 Root Cause Identification**: Pinpoints fault origins with high accuracy using causal analysis
- **⚡ Real-time Processing**: Builds and analyzes CTH graphs in real-time for immediate insights
- **🔧 Intelligent Remediation**: Generates context-aware, executable repair commands
- **📊 Impact Assessment**: Quantifies fault scope and propagation velocity
- **🧩 Pattern Recognition**: Identifies resilience patterns and potential conflicts
- **🤖 LLM Integration**: Combines graph analysis with natural language reasoning

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

#### 2. Web Interface (includes CTH API)
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

### Traditional Kubernetes Interactions

```
> Why is my nginx pod not ready?
> Show me all failed pods in the default namespace
> Scale my deployment to 3 replicas
> What's wrong with my service?
> Check the logs of pod nginx-xxx
```

### CTH Framework Usage

#### 1. Building CTH Graph from Observability Data

```bash
# Via Chat Interface
> Please build CTH graph using the following observability data: {JSON data}

# Via API
curl -X POST http://localhost:5000/api/cth/build \
  -H "Content-Type: application/json" \
  -d @examples/cth_sample_data.json
```

#### 2. Intelligent Fault Analysis

```bash
# Via Chat Interface
> Analyze this alert: checkout service response time exceeds 5 seconds
> Find fault propagation paths starting from service:checkout

# Via API
curl -X POST http://localhost:5000/api/cth/analyze \
  -H "Content-Type: application/json" \
  -d '{"alert_info": "Service checkout experiencing high latency"}'
```

#### 3. Generating Remediation Plans

```bash
# Via Chat Interface
> Generate remediation plan for database connection pool exhaustion issue

# Via API
curl -X POST http://localhost:5000/api/cth/remediation \
  -H "Content-Type: application/json" \
  -d '{"alert_info": "Database connection pool exhausted"}'
```

#### 4. Querying CTH Graph

```bash
# Via Chat Interface
> Query anomaly events related to service:payment
> Get CTH graph statistics

# Via API
curl -X POST http://localhost:5000/api/cth/query \
  -H "Content-Type: application/json" \
  -d '{"query_type": "find_propagation_paths", "start_node": "service:checkout"}'
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

## CTH API Endpoints

The CTH framework provides RESTful API endpoints for integration with external systems:

**🔒 Session Isolation Support**: All API endpoints now support session isolation, ensuring data security during concurrent multi-user access.

### Core Endpoints

- `GET /api/cth/health` - Health check
- `POST /api/cth/build` - Build CTH graph from observability data (supports session isolation)
- `POST /api/cth/analyze` - Perform fault analysis (supports session isolation)
- `POST /api/cth/query` - Query CTH graph (supports session isolation)
- `POST /api/cth/remediation` - Generate remediation plans (supports session isolation)
- `GET /api/cth/status` - Get CTH system status (supports session isolation)
- `POST /api/cth/clear` - Clear CTH graph data (supports session isolation)

### Session Management Endpoints

- `GET /api/cth/sessions` - List all active sessions
- `DELETE /api/cth/sessions/{session_id}` - Delete specific session
- `POST /api/cth/sessions/clear-all` - Clear all sessions

## License

This project is licensed under the terms of the Apache-2.0 license. See the [`LICENSE`](./LICENSE) file for details.
