import os
from typing import Optional
from langchain_core.prompts import PromptTemplate
from langchain.agents import create_react_agent, AgentExecutor
from langchain.memory import ConversationBufferMemory
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
            RequestsGet(allow_dangerous_requests=True)
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

    def invoke(self, input: str):
        return self.agent.invoke({
            "input": input,
            "chat_history": self.memory.buffer,
        })
    
    def stream(self, input_data):
        """Stream the agent's response including intermediate steps"""
        # Handle both string and dict input
        if isinstance(input_data, dict):
            input_str = input_data.get("input", "")
        else:
            input_str = input_data
            
        return self.agent.stream({
            "input": input_str,
            "chat_history": self.memory.buffer,
        })

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
