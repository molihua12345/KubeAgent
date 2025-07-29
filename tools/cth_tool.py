"""CTH Tool for LangChain Integration

Provides CTH (Causal-Temporal Hypergraph) functionality as LangChain tools
for integration with the existing KubeAgent framework.
"""

from typing import Optional, Type, Any, Dict, List
from pydantic import Field, BaseModel
from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.tools import BaseTool
import json

from cth import CTHAgent, CTHGraph, CTHBuilder, PropagationAnalyzer


class CTHBuildInput(BaseModel):
    """Input schema for CTH graph building."""
    
    observability_data: str = Field(
        ...,
        description="JSON string containing observability data with traces, metrics, and logs"
    )


class CTHAnalysisInput(BaseModel):
    """Input schema for CTH analysis."""
    
    alert_info: str = Field(
        ...,
        description="Alert information or anomaly description to analyze"
    )


class CTHQueryInput(BaseModel):
    """Input schema for CTH graph queries."""
    
    query_type: str = Field(
        ...,
        description="Type of query: 'query_nodes_by_entity', 'query_anomalous_events', 'find_propagation_paths', or 'get_graph_statistics'"
    )
    entity_name: Optional[str] = Field(
        None,
        description="Entity name for node queries"
    )
    start_node: Optional[str] = Field(
        None,
        description="Starting node for propagation path analysis"
    )
    severity_level: Optional[str] = Field(
        None,
        description="Severity level filter: 'normal', 'warning', 'error', 'critical'"
    )
    max_paths: Optional[int] = Field(
        5,
        description="Maximum number of propagation paths to return"
    )


class CTHBuildTool(BaseTool):
    """Tool for building CTH graph from observability data."""
    
    name: str = "cth_build"
    description: str = (
        "Build Causal-Temporal Hypergraph (CTH) from observability data. "
        "Input should be JSON string containing 'traces', 'metrics', and 'logs' arrays. "
        "This tool constructs the CTH graph that can be used for fault propagation analysis."
        "the example param format of [observability_data] is as follows:"
        """{"traces":[{"trace_id":"test-trace-001","spans":[{"service":"frontend","operation":"handle-request","start_time":"2024-01-15T10:00:00Z","end_time":"2024-01-15T10:00:02Z","status":"error","tags":{"pod":"frontend-pod-123","node":"worker-1"}}]}],"metrics":[{"entity":"frontend","metric_name":"response_time","value":2500,"timestamp":"2024-01-15T10:00:00Z","is_anomalous":"True","tags":{"pod":"frontend-pod-123"}}],"logs":[{"entity":"frontend","message":"Request failed: backend service timeout","level":"error","timestamp":"2024-01-15T10:00:02Z","tags":{"pod":"frontend-pod-123","trace_id":"test-trace-001"}}]}"""
    )
    args_schema: Type[BaseModel] = CTHBuildInput
    cth_agent: CTHAgent
    
    def __init__(self, cth_agent: CTHAgent):
        super().__init__(cth_agent=cth_agent)
    
    def _run(
        self,
        observability_data: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Build CTH graph from observability data."""
        try:
            # Parse JSON data
            data = json.loads(observability_data)
            
            # Build CTH graph
            result = self.cth_agent.build_cth_from_data(data)
            
            if result['success']:
                stats = result['statistics']
                return (
                    f"✅ CTH图构建成功!\n"
                    f"📊 统计信息:\n"
                    f"- 超边数量: {stats['total_edges']}\n"
                    f"- 节点数量: {stats['total_nodes']}\n"
                    f"- 时间跨度: {stats['time_span_seconds']:.1f} 秒\n"
                    f"- 最早事件: {stats.get('earliest_event', 'N/A')}\n"
                    f"- 最新事件: {stats.get('latest_event', 'N/A')}\n\n"
                    f"CTH图已准备就绪，可以进行故障传播分析。"
                )
            else:
                error_msg = "\n".join(result['errors'])
                return f"❌ CTH图构建失败:\n{error_msg}"
        
        except json.JSONDecodeError as e:
            return f"❌ JSON解析错误: {str(e)}"
        except Exception as e:
            return f"❌ CTH构建过程出错: {str(e)}"


class CTHAnalysisTool(BaseTool):
    """Tool for performing CTH-based fault analysis."""
    
    name: str = "cth_analyze"
    description: str = (
        "Perform intelligent fault analysis using CTH (Causal-Temporal Hypergraph). "
        "Analyzes alert information to identify root causes, propagation paths, and impact scope. "
        "Requires CTH graph to be built first using cth_build tool."
    )
    args_schema: Type[BaseModel] = CTHAnalysisInput
    cth_agent: CTHAgent
    
    def __init__(self, cth_agent: CTHAgent):
        super().__init__(cth_agent=cth_agent)
    
    def _run(
        self,
        alert_info: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Perform CTH-based fault analysis."""
        try:
            if not self.cth_agent.current_cth_graph:
                return "❌ 错误: 请先使用 cth_build 工具构建CTH图"
            
            # Perform interactive diagnosis
            analysis_steps = []
            final_result = None
            
            for step in self.cth_agent.interactive_diagnosis(alert_info):
                if isinstance(step, str) and step.startswith(("🤔", "📊", "🎯", "🔍", "📈", "⚠️", "✅")):
                    analysis_steps.append(step)
                else:
                    final_result = step
            
            # Combine analysis steps and final result
            result_parts = [
                "🔍 CTH智能故障分析结果:",
                "",
                "## 分析过程:"
            ]
            result_parts.extend(analysis_steps)
            
            if final_result:
                result_parts.extend([
                    "",
                    "## 详细分析报告:",
                    final_result
                ])
            
            return "\n".join(result_parts)
        
        except Exception as e:
            return f"❌ CTH分析过程出错: {str(e)}"


class CTHQueryTool(BaseTool):
    """Tool for querying CTH graph data."""
    
    name: str = "cth_query"
    description: str = (
        "Query CTH graph for specific information. "
        "Supports queries for nodes, anomalous events, propagation paths, and statistics. "
        "Requires CTH graph to be built first."
    )
    args_schema: Type[BaseModel] = CTHQueryInput
    cth_agent: CTHAgent
    
    def __init__(self, cth_agent: CTHAgent):
        super().__init__(cth_agent=cth_agent)
    
    def _run(
        self,
        query_type: str,
        entity_name: Optional[str] = None,
        start_node: Optional[str] = None,
        severity_level: Optional[str] = None,
        max_paths: Optional[int] = 5,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Query CTH graph."""
        try:
            if not self.cth_agent.current_cth_graph:
                return "❌ 错误: 请先使用 cth_build 工具构建CTH图"
            
            # Prepare query parameters
            kwargs = {}
            if entity_name:
                kwargs['entity_name'] = entity_name
            if start_node:
                kwargs['start_node'] = start_node
            if severity_level:
                kwargs['severity_level'] = severity_level
            if max_paths:
                kwargs['max_paths'] = max_paths
            
            # Execute query
            result = self.cth_agent.query_cth_graph(query_type, **kwargs)
            
            if 'error' in result:
                return f"❌ 查询错误: {result['error']}"
            
            # Format results based on query type
            return self._format_query_result(query_type, result)
        
        except Exception as e:
            return f"❌ CTH查询过程出错: {str(e)}"
    
    def _format_query_result(self, query_type: str, result: Dict[str, Any]) -> str:
        """Format query results for display."""
        if query_type == 'query_nodes_by_entity':
            entity = result.get('entity', '')
            count = result.get('hyperedges_count', 0)
            if count == 0:
                return f"📊 实体 '{entity}' 未找到相关超边"
            
            output = [f"📊 实体 '{entity}' 相关信息:", f"- 相关超边数量: {count}"]
            
            hyperedges = result.get('hyperedges', [])
            for i, edge in enumerate(hyperedges[:3]):  # Show first 3
                output.append(f"\n超边 {i+1}:")
                output.append(f"  - 时间: {edge.get('timestamp', 'N/A')}")
                output.append(f"  - 严重程度: {edge.get('severity', 'normal')}")
                output.append(f"  - 涉及节点: {len(edge.get('nodes', []))} 个")
                if edge.get('metrics'):
                    output.append(f"  - 异常指标: {len(edge.get('metrics', []))} 个")
                if edge.get('logs'):
                    output.append(f"  - 关键日志: {len(edge.get('logs', []))} 个")
            
            if count > 3:
                output.append(f"\n... 还有 {count - 3} 个超边")
            
            return "\n".join(output)
        
        elif query_type == 'query_anomalous_events':
            count = result.get('anomalous_events_count', 0)
            if count == 0:
                return "📊 未找到异常事件"
            
            output = [f"📊 异常事件分析:", f"- 异常事件数量: {count}"]
            
            events = result.get('events', [])
            severity_counts = {}
            for event in events:
                sev = event.get('severity', 'normal')
                severity_counts[sev] = severity_counts.get(sev, 0) + 1
            
            output.append("\n严重程度分布:")
            for sev, cnt in severity_counts.items():
                output.append(f"  - {sev}: {cnt} 个")
            
            # Show recent events
            recent_events = sorted(events, key=lambda x: x.get('timestamp', ''), reverse=True)[:3]
            output.append("\n最近异常事件:")
            for i, event in enumerate(recent_events):
                output.append(f"  {i+1}. {event.get('timestamp', 'N/A')} - {event.get('severity', 'normal')}")
                if event.get('nodes'):
                    output.append(f"     涉及: {', '.join(event.get('nodes', [])[:3])}")
            
            return "\n".join(output)
        
        elif query_type == 'find_propagation_paths':
            start_node = result.get('start_node', '')
            count = result.get('paths_found', 0)
            
            if count == 0:
                return f"📊 从节点 '{start_node}' 未找到故障传播路径"
            
            output = [f"📊 故障传播路径分析:", f"- 起始节点: {start_node}", f"- 发现路径数量: {count}"]
            
            paths = result.get('paths', [])
            for i, path in enumerate(paths[:3]):  # Show first 3 paths
                summary = path.get('summary', {})
                output.append(f"\n路径 {i+1}:")
                output.append(f"  - 概率: {summary.get('probability', 0):.3f}")
                output.append(f"  - 路径长度: {summary.get('path_length', 0)} 步")
                output.append(f"  - 持续时间: {summary.get('total_duration', 0):.1f} 秒")
                output.append(f"  - 影响节点: {summary.get('node_count', 0)} 个")
                
                severity_prog = summary.get('severity_progression', [])
                if severity_prog:
                    output.append(f"  - 严重程度变化: {' → '.join(severity_prog)}")
            
            if count > 3:
                output.append(f"\n... 还有 {count - 3} 条路径")
            
            return "\n".join(output)
        
        elif query_type == 'get_graph_statistics':
            output = ["📊 CTH图统计信息:"]
            output.append(f"- 超边总数: {result.get('total_edges', 0)}")
            output.append(f"- 节点总数: {result.get('total_nodes', 0)}")
            output.append(f"- 时间跨度: {result.get('time_span_seconds', 0):.1f} 秒")
            
            if result.get('earliest_event'):
                output.append(f"- 最早事件: {result.get('earliest_event')}")
            if result.get('latest_event'):
                output.append(f"- 最新事件: {result.get('latest_event')}")
            
            output.append(f"- 创建时间: {result.get('created_at', 'N/A')}")
            output.append(f"- 版本: {result.get('version', 'N/A')}")
            
            return "\n".join(output)
        
        else:
            return f"📊 查询结果:\n{json.dumps(result, indent=2, ensure_ascii=False)}"


class CTHRemediationTool(BaseTool):
    """Tool for generating remediation plans based on CTH analysis."""
    
    name: str = "cth_remediation"
    description: str = (
        "Generate detailed remediation plan based on CTH fault analysis. "
        "Provides executable commands, incident reports, and prevention recommendations. "
        "Should be used after performing CTH analysis."
    )
    args_schema: Type[BaseModel] = CTHAnalysisInput  # Reuse same input schema
    cth_agent: CTHAgent
    last_analysis_result: Optional[str] = None
    last_propagation_paths: List = []
    last_scope_analysis: Dict[str, Any] = {}
    
    def __init__(self, cth_agent: CTHAgent):
        super().__init__(
            cth_agent=cth_agent,
            last_analysis_result=None,
            last_propagation_paths=[],
            last_scope_analysis={}
        )
    
    def _run(
        self,
        alert_info: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Generate remediation plan."""
        try:
            if not self.cth_agent.current_cth_graph:
                return "❌ 错误: 请先使用 cth_build 工具构建CTH图"
            
            # If we don't have recent analysis results, perform analysis first
            if not self.last_analysis_result:
                # Extract anomaly nodes and find propagation paths
                anomaly_nodes = self.cth_agent._extract_anomaly_nodes_from_alert(alert_info)
                
                all_paths = []
                for node in anomaly_nodes:
                    paths = self.cth_agent.propagation_analyzer.find_propagation_paths(
                        self.cth_agent.current_cth_graph, node
                    )
                    all_paths.extend(paths)
                
                if all_paths:
                    self.last_propagation_paths = all_paths
                    self.last_scope_analysis = self.cth_agent.propagation_analyzer.quantify_propagation_scope(all_paths)
                    self.last_analysis_result = f"基于告警信息的快速分析: {alert_info}"
                else:
                    return "⚠️ 未找到足够的故障传播信息来生成修复方案"
            
            # Generate remediation plan
            remediation_plan = self.cth_agent.generate_remediation_plan(
                self.last_analysis_result,
                self.last_propagation_paths,
                self.last_scope_analysis
            )
            
            # Clear cached results
            self.last_analysis_result = None
            self.last_propagation_paths = []
            self.last_scope_analysis = {}
            
            return f"🔧 CTH修复方案:\n\n{remediation_plan}"
        
        except Exception as e:
            return f"❌ 修复方案生成过程出错: {str(e)}"
    
    def set_analysis_context(self, analysis_result: str, propagation_paths: List, scope_analysis: Dict[str, Any]):
        """Set analysis context for remediation generation."""
        self.last_analysis_result = analysis_result
        self.last_propagation_paths = propagation_paths
        self.last_scope_analysis = scope_analysis


def create_cth_tools(cth_agent: Optional[CTHAgent] = None) -> List[BaseTool]:
    """Create CTH tools for LangChain integration.
    
    Args:
        cth_agent: CTH agent instance. If None, creates a new one.
    
    Returns:
        List of CTH tools
    """
    if cth_agent is None:
        cth_agent = CTHAgent()
    
    return [
        CTHBuildTool(cth_agent),
        CTHAnalysisTool(cth_agent),
        CTHQueryTool(cth_agent),
        CTHRemediationTool(cth_agent)
    ]


# For backward compatibility
CTHTool = CTHBuildTool