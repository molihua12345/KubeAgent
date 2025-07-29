import os
from typing import Optional
from langchain_core.prompts import PromptTemplate
from langchain.agents import create_react_agent, AgentExecutor
from langchain.memory import ConversationBufferMemory
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

from .prompt import REACT_PROMPT
from tools import *
from cth import CTHAgent

class KubeAgent:
    """KubeAgent is an AI agent that helps users with Kubernetes issues.

    Init args — completion params:
    - llm: llm model
    - debug_level: debug level for the agent, 0 is no debug, 1 is verbose, 2 is verbose with intermediate steps
    """

    name: str = "KubeAgent"

    def __init__(self, llm: BaseChatModel= None, debug_level: Optional[int] = None):
        # Initialize CTH agent
        self.cth_agent = CTHAgent(llm)
        
        # Create tools including CTH tools
        self.tools = [
            KubeTool(), 
            KubeToolWithApprove(), 
            human_console_input(), 
            create_search_tool(), 
            RequestsGet(allow_dangerous_requests=True),
            create_database_query_tool()
        ] + create_cth_tools(self.cth_agent)
        
        # 如果没有提供llm，则使用DeepSeek API
        if llm is None:
            llm = ChatOpenAI(
                model="deepseek-chat",
                temperature=0.7,
                base_url="https://api.deepseek.com",
                api_key=os.getenv("DEEPSEEK_API_KEY"),
            )
        
        # Create prompt with tools
        self.prompt = PromptTemplate.from_template(REACT_PROMPT, tools=self.tools)
        
        self.memory = ConversationBufferMemory(memory_key="chat_history", output_key="output")
        self.max_history_length = 20  # 限制历史记录最大长度
        self.conversation_pairs = []  # 存储简化的对话对

        agent = create_react_agent(llm, self.tools, self.prompt)

        verbose = False
        return_intermediate_steps = False
        if debug_level is None:
            debug_level = int(os.getenv("DEBUG_LEVEL", "1"))

        if debug_level == 1:
            verbose = True
        elif debug_level >= 2:
            verbose = True
            return_intermediate_steps = True

        self.agent = AgentExecutor(
            name=self.name,
            agent=agent,
            memory=self.memory,
            tools=self.tools,
            return_intermediate_steps=return_intermediate_steps,
            handle_parsing_errors=True,
            verbose=verbose,
        )

    def _manage_history(self):
        """管理历史记录长度，保持在限制范围内"""
        if len(self.conversation_pairs) > self.max_history_length:
            # 移除最旧的对话对，保留最新的对话
            self.conversation_pairs = self.conversation_pairs[-self.max_history_length:]
            
        # 重建memory中的消息
        self.memory.clear()
        for pair in self.conversation_pairs:
            self.memory.chat_memory.add_user_message(pair['user'])
            self.memory.chat_memory.add_ai_message(pair['ai'])
    
    def invoke(self, input: str):
        result = self.agent.invoke({
            "input": input,
            "chat_history": self.memory.buffer,
        })
        
        # 只保存用户输入和AI的最终输出到简化历史记录
        self.conversation_pairs.append({
            'user': input,
            'ai': result.get('output', '')
        })
        
        # 管理历史记录长度
        self._manage_history()
        
        return result
    
    def stream(self, input_data):
        """Stream the agent's response including intermediate steps"""
        # Handle both string and dict input
        if isinstance(input_data, dict):
            input_str = input_data.get("input", "")
        else:
            input_str = input_data
            
        # 收集流式响应的最终输出
        final_output = ""
        stream_generator = self.agent.stream({
            "input": input_str,
            "chat_history": self.memory.buffer,
        })
        
        # 创建一个生成器来处理流式响应并收集最终输出
        def process_stream():
            nonlocal final_output
            for chunk in stream_generator:
                if 'output' in chunk:
                    final_output = chunk['output']
                yield chunk
            
            # 流式响应结束后，保存到简化历史记录
            if final_output:
                self.conversation_pairs.append({
                    'user': input_str,
                    'ai': final_output
                })
                self._manage_history()
        
        return process_stream()

    def get_chat_messages(self):
        return self.memory.chat_memory.messages
    
    def get_conversation_history(self):
        """Get conversation history in a format suitable for web interface"""
        messages = []
        for msg in self.memory.chat_memory.messages:
            if hasattr(msg, 'content'):
                # Determine if it's a user or AI message based on message type
                is_user = msg.__class__.__name__ == 'HumanMessage'
                messages.append({
                    'content': msg.content,
                    'is_user': is_user
                })
        return messages
    
    def clear_conversation_history(self):
        """Clear the conversation history"""
        self.memory.clear()
        self.conversation_pairs.clear()
