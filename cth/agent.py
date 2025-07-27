"""CTH Agent Module

Implements LLM-driven intelligent diagnosis and remediation based on CTH analysis.
Integrates with the existing KubeAgent framework.
"""

from typing import Dict, List, Any, Optional, Generator
from datetime import datetime
import json

from langchain_core.prompts import PromptTemplate
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from .graph import CTHGraph, Hyperedge
from .builder import CTHBuilder
from .analyzer import PropagationAnalyzer, PropagationPath


class CTHAgent:
    """LLM-powered agent for CTH-based fault diagnosis and remediation.
    
    Implements the ReAct/RAG framework where CTH serves as the external knowledge base
    that the LLM agent can query and reason about.
    """
    
    def __init__(self, llm: Optional[BaseChatModel] = None):
        """
        Initialize CTH Agent.
        
        Args:
            llm: Language model for reasoning. If None, uses DeepSeek by default.
        """
        if llm is None:
            import os
            llm = ChatOpenAI(
                model="deepseek-chat",
                temperature=0.3,  # Lower temperature for more focused analysis
                base_url="https://api.deepseek.com",
                api_key=os.getenv("DEEPSEEK_API_KEY"),
            )
        
        self.llm = llm
        self.cth_builder = CTHBuilder()
        self.propagation_analyzer = PropagationAnalyzer()
        self.current_cth_graph: Optional[CTHGraph] = None
        
        # Initialize prompts for different analysis tasks
        self._init_prompts()
    
    def _init_prompts(self):
        """Initialize prompt templates for different analysis tasks."""
        
        # Resilience pattern identification prompt
        self.pattern_analysis_prompt = PromptTemplate.from_template(
            """你是一位资深的站点可靠性工程师(SRE)。请分析以下故障传播路径数据，识别其中可能存在的韧性策略模式及其潜在冲突。

故障传播路径信息:
{propagation_paths}

相关的可观测性数据:
{observability_data}

请重点分析以下方面:
1. 识别重试(Retry)模式的证据
2. 识别超时(Timeout)机制的触发
3. 识别熔断(Circuit Breaker)模式
4. 识别舱壁(Bulkhead)隔离模式
5. 分析这些韧性策略之间是否存在冲突

请提供详细的分析过程和结论，包括:
- 发现的韧性模式
- 模式冲突分析
- 改进建议
"""
        )
        
        # Interactive diagnosis prompt
        self.diagnosis_prompt = PromptTemplate.from_template(
            """你是一个基于CTH(因果-时序超图)的智能诊断助手。你可以通过分析CTH图来诊断云原生系统故障。

当前告警信息:
{alert_info}

CTH图统计信息:
{cth_statistics}

你的任务是:
1. 分析告警的根本原因
2. 追踪故障传播路径
3. 评估影响范围
4. 提供修复建议

请开始你的分析。如果需要更多信息，请说明你需要什么数据。
"""
        )
        
        # Remediation generation prompt
        self.remediation_prompt = PromptTemplate.from_template(
            """基于以下CTH分析结果，请生成具体的修复方案和报告。

根本原因分析:
{root_cause_analysis}

故障传播路径:
{propagation_paths}

影响范围分析:
{scope_analysis}

请生成:
1. 可执行的kubectl/helm命令来修复问题
2. 详细的故障报告(适合JIRA工单)
3. 预防措施建议
4. 监控改进建议

确保所有建议都是安全的、可执行的，并包含必要的验证步骤。
"""
        )
    
    def build_cth_from_data(self, observability_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build CTH graph from observability data and return construction results.
        
        Args:
            observability_data: JSON data containing traces, metrics, and logs
        
        Returns:
            Dictionary containing construction results and any validation errors
        """
        # Validate input data
        validation_errors = self.cth_builder.validate_input_data(observability_data)
        if validation_errors:
            return {
                'success': False,
                'errors': validation_errors,
                'cth_graph': None
            }
        
        try:
            # Build CTH graph
            self.current_cth_graph = self.cth_builder.build_cth_from_json(observability_data)
            
            return {
                'success': True,
                'errors': [],
                'cth_graph': self.current_cth_graph.to_dict(),
                'statistics': self.current_cth_graph.get_statistics()
            }
        
        except Exception as e:
            return {
                'success': False,
                'errors': [f"CTH construction failed: {str(e)}"],
                'cth_graph': None
            }
    
    def analyze_resilience_patterns(self, propagation_paths: List[PropagationPath], 
                                  observability_data: Dict[str, Any]) -> str:
        """
        Analyze resilience patterns and conflicts in propagation paths.
        
        Args:
            propagation_paths: List of fault propagation paths
            observability_data: Original observability data for context
        
        Returns:
            LLM analysis of resilience patterns and conflicts
        """
        # Prepare data for LLM analysis
        paths_summary = []
        for i, path in enumerate(propagation_paths):
            paths_summary.append({
                'path_id': i + 1,
                'summary': path.get_path_summary(),
                'hyperedges': [{
                    'nodes': list(edge.nodes),
                    'timestamp': edge.timestamp.isoformat(),
                    'severity': edge.severity,
                    'trace_id': edge.trace_id,
                    'metrics': list(edge.metrics),
                    'logs': list(edge.logs)
                } for edge in path.hyperedges]
            })
        
        # Format observability data for context
        obs_summary = {
            'total_traces': len(observability_data.get('traces', [])),
            'total_metrics': len(observability_data.get('metrics', [])),
            'total_logs': len(observability_data.get('logs', [])),
            'sample_traces': observability_data.get('traces', [])[:3],  # First 3 traces
            'anomalous_metrics': [m for m in observability_data.get('metrics', []) if m.get('is_anomalous')],
            'error_logs': [l for l in observability_data.get('logs', []) if l.get('level', '').lower() in ['error', 'critical']]
        }
        
        # Generate LLM analysis
        prompt = self.pattern_analysis_prompt.format(
            propagation_paths=json.dumps(paths_summary, indent=2, ensure_ascii=False),
            observability_data=json.dumps(obs_summary, indent=2, ensure_ascii=False)
        )
        
        response = self.llm.invoke(prompt)
        return response.content
    
    def interactive_diagnosis(self, alert_info: str) -> Generator[str, None, str]:
        """
        Perform interactive diagnosis using ReAct framework.
        
        Args:
            alert_info: Initial alert information
        
        Yields:
            Intermediate reasoning steps
        
        Returns:
            Final diagnosis result
        """
        if not self.current_cth_graph:
            yield "❌ 错误: 没有可用的CTH图数据。请先构建CTH图。"
            return "诊断失败：缺少CTH图数据"
        
        # Initial reasoning
        cth_stats = self.current_cth_graph.get_statistics()
        
        initial_prompt = self.diagnosis_prompt.format(
            alert_info=alert_info,
            cth_statistics=json.dumps(cth_stats, indent=2, ensure_ascii=False)
        )
        
        yield "🤔 开始分析告警信息和CTH图数据..."
        
        # Step 1: Initial analysis
        response = self.llm.invoke(initial_prompt)
        initial_analysis = response.content
        yield f"📊 初步分析:\n{initial_analysis}"
        
        # Step 2: Extract potential anomaly nodes from alert
        anomaly_nodes = self._extract_anomaly_nodes_from_alert(alert_info)
        yield f"🎯 识别到潜在异常节点: {anomaly_nodes}"
        
        # Step 3: Find propagation paths for each anomaly node
        all_paths = []
        for node in anomaly_nodes:
            paths = self.propagation_analyzer.find_propagation_paths(self.current_cth_graph, node)
            all_paths.extend(paths)
            if paths:
                yield f"🔍 从节点 {node} 发现 {len(paths)} 条传播路径"
        
        if not all_paths:
            yield "⚠️ 未发现明显的故障传播路径，可能是孤立事件"
            return "未发现故障传播路径"
        
        # Step 4: Analyze propagation scope
        scope_analysis = self.propagation_analyzer.quantify_propagation_scope(all_paths)
        yield f"📈 影响范围分析: 共影响 {scope_analysis['total_affected_nodes']} 个节点"
        
        # Step 5: Generate comprehensive analysis
        final_analysis = self._generate_comprehensive_analysis(
            alert_info, initial_analysis, all_paths, scope_analysis
        )
        
        yield "✅ 诊断完成"
        return final_analysis
    
    def generate_remediation_plan(self, diagnosis_result: str, 
                                propagation_paths: List[PropagationPath],
                                scope_analysis: Dict[str, Any]) -> str:
        """
        Generate detailed remediation plan based on diagnosis results.
        
        Args:
            diagnosis_result: Result from interactive diagnosis
            propagation_paths: Identified propagation paths
            scope_analysis: Scope analysis results
        
        Returns:
            Comprehensive remediation plan
        """
        # Prepare data for remediation prompt
        paths_data = [path.to_dict() for path in propagation_paths]
        
        prompt = self.remediation_prompt.format(
            root_cause_analysis=diagnosis_result,
            propagation_paths=json.dumps(paths_data, indent=2, ensure_ascii=False),
            scope_analysis=json.dumps(scope_analysis, indent=2, ensure_ascii=False)
        )
        
        response = self.llm.invoke(prompt)
        return response.content
    
    def _extract_anomaly_nodes_from_alert(self, alert_info: str) -> List[str]:
        """
        Extract potential anomaly nodes from alert information.
        
        This is a simple heuristic-based extraction. In production,
        this could be enhanced with NER models.
        """
        import re
        
        nodes = []
        
        # Look for service names
        service_pattern = r'service[:\s]+([\w-]+)'
        services = re.findall(service_pattern, alert_info, re.IGNORECASE)
        nodes.extend([f"service:{s}" for s in services])
        
        # Look for pod names
        pod_pattern = r'pod[:\s]+([\w-]+)'
        pods = re.findall(pod_pattern, alert_info, re.IGNORECASE)
        nodes.extend([f"pod:{p}" for p in pods])
        
        # Look for node names
        node_pattern = r'node[:\s]+([\w-]+)'
        node_names = re.findall(node_pattern, alert_info, re.IGNORECASE)
        nodes.extend([f"node:{n}" for n in node_names])
        
        # If no specific nodes found, try to extract any entity names
        if not nodes:
            # Look for common Kubernetes resource patterns
            entity_pattern = r'([\w-]+(?:-[\w]+)*(?:-\d+)?(?:-[a-f0-9]{5,})?)'  
            entities = re.findall(entity_pattern, alert_info)
            # Filter out common words and keep likely resource names
            likely_resources = [e for e in entities if len(e) > 3 and '-' in e]
            nodes.extend([f"entity:{e}" for e in likely_resources[:3]])  # Limit to 3
        
        return list(set(nodes))  # Remove duplicates
    
    def _generate_comprehensive_analysis(self, alert_info: str, initial_analysis: str,
                                       propagation_paths: List[PropagationPath],
                                       scope_analysis: Dict[str, Any]) -> str:
        """
        Generate comprehensive analysis combining all diagnosis results.
        """
        analysis_parts = [
            "# 故障诊断综合分析报告",
            f"\n## 告警信息\n{alert_info}",
            f"\n## 初步分析\n{initial_analysis}",
            f"\n## 传播路径分析\n发现 {len(propagation_paths)} 条故障传播路径:"
        ]
        
        # Add path summaries
        for i, path in enumerate(propagation_paths[:3]):  # Show top 3 paths
            summary = path.get_path_summary()
            analysis_parts.append(
                f"\n### 路径 {i+1} (概率: {summary['probability']:.2f})\n"
                f"- 持续时间: {summary['total_duration']:.1f} 秒\n"
                f"- 影响节点: {summary['node_count']} 个\n"
                f"- 严重程度变化: {' → '.join(summary['severity_progression'])}"
            )
        
        # Add scope analysis
        analysis_parts.extend([
            f"\n## 影响范围分析",
            f"- 总影响节点数: {scope_analysis['total_affected_nodes']}",
            f"- 影响范围严重程度: {scope_analysis['scope_severity']}",
            f"- 传播速度: {scope_analysis['propagation_velocity']:.2f} 节点/秒"
        ])
        
        # Add node type breakdown
        node_types = scope_analysis.get('node_type_counts', {})
        if node_types:
            analysis_parts.append("\n### 受影响组件类型:")
            for node_type, count in node_types.items():
                analysis_parts.append(f"- {node_type}: {count} 个")
        
        # Add core components
        core_components = scope_analysis.get('core_components', [])
        if core_components:
            analysis_parts.append("\n### 核心影响组件:")
            for comp in core_components[:3]:
                analysis_parts.append(
                    f"- {', '.join(comp['nodes'])} (中心性得分: {comp['centrality_score']:.2f})"
                )
        
        return "\n".join(analysis_parts)
    
    def get_cth_query_interface(self) -> Dict[str, Any]:
        """
        Get interface for querying CTH graph (for tool integration).
        
        Returns:
            Dictionary of available query methods and their descriptions
        """
        return {
            'query_nodes_by_entity': {
                'description': '根据实体名称查询相关的超边',
                'parameters': ['entity_name', 'time_range (optional)']
            },
            'query_anomalous_events': {
                'description': '查询异常事件和相关超边',
                'parameters': ['severity_level (optional)', 'time_range (optional)']
            },
            'find_propagation_paths': {
                'description': '查找从指定节点开始的故障传播路径',
                'parameters': ['start_node', 'max_paths (optional)']
            },
            'get_graph_statistics': {
                'description': '获取CTH图的统计信息',
                'parameters': []
            }
        }
    
    def query_cth_graph(self, query_type: str, **kwargs) -> Dict[str, Any]:
        """
        Query CTH graph with specified parameters.
        
        This method serves as a tool interface for LLM agents.
        
        Args:
            query_type: Type of query to perform
            **kwargs: Query parameters
        
        Returns:
            Query results
        """
        if not self.current_cth_graph:
            return {'error': 'No CTH graph available'}
        
        try:
            if query_type == 'query_nodes_by_entity':
                entity_name = kwargs.get('entity_name', '')
                hyperedges = self.current_cth_graph.get_hyperedges_containing(entity_name)
                return {
                    'entity': entity_name,
                    'hyperedges_count': len(hyperedges),
                    'hyperedges': [edge.to_dict() for edge in hyperedges]
                }
            
            elif query_type == 'query_anomalous_events':
                severity = kwargs.get('severity_level', None)
                anomalous_edges = []
                for edge in self.current_cth_graph.hyperedges.values():
                    if severity is None or edge.severity == severity:
                        if edge.metrics or edge.logs or edge.severity != 'normal':
                            anomalous_edges.append(edge)
                
                return {
                    'anomalous_events_count': len(anomalous_edges),
                    'events': [edge.to_dict() for edge in anomalous_edges]
                }
            
            elif query_type == 'find_propagation_paths':
                start_node = kwargs.get('start_node', '')
                max_paths = kwargs.get('max_paths', 5)
                paths = self.propagation_analyzer.find_propagation_paths(
                    self.current_cth_graph, start_node, max_paths
                )
                return {
                    'start_node': start_node,
                    'paths_found': len(paths),
                    'paths': [path.to_dict() for path in paths]
                }
            
            elif query_type == 'get_graph_statistics':
                return self.current_cth_graph.get_statistics()
            
            else:
                return {'error': f'Unknown query type: {query_type}'}
        
        except Exception as e:
            return {'error': f'Query failed: {str(e)}'}