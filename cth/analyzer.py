"""CTH Propagation Analyzer Module

Implements fault propagation path analysis and scope quantification
based on the CTH framework.
"""

from typing import List, Dict, Set, Any, Optional, Tuple
from datetime import datetime, timedelta
import networkx as nx
from collections import defaultdict, deque
import math

from .graph import CTHGraph, Hyperedge


class PropagationPath:
    """Represents a fault propagation path as a sequence of hyperedges."""
    
    def __init__(self, hyperedges: List[Hyperedge], probability: float = 0.0):
        self.hyperedges = hyperedges
        self.probability = probability
        self.total_nodes = set()
        for edge in hyperedges:
            self.total_nodes.update(edge.nodes)
    
    def get_path_summary(self) -> Dict[str, Any]:
        """Get summary information about the propagation path."""
        if not self.hyperedges:
            return {}
        
        return {
            'path_length': len(self.hyperedges),
            'start_time': self.hyperedges[0].timestamp.isoformat(),
            'end_time': self.hyperedges[-1].timestamp.isoformat(),
            'total_duration': (self.hyperedges[-1].timestamp - self.hyperedges[0].timestamp).total_seconds(),
            'affected_nodes': list(self.total_nodes),
            'node_count': len(self.total_nodes),
            'probability': self.probability,
            'severity_progression': [edge.severity for edge in self.hyperedges],
            'edge_ids': [edge.edge_id for edge in self.hyperedges]
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert path to dictionary representation."""
        return {
            'summary': self.get_path_summary(),
            'hyperedges': [edge.to_dict() for edge in self.hyperedges]
        }


class PropagationAnalyzer:
    """Analyzer for fault propagation paths and impact scope in CTH.
    
    Implements Algorithm 2: Find_Propagation_Path and related analysis methods.
    """
    
    def __init__(self, max_path_length: int = 10, min_probability: float = 0.1):
        """
        Initialize propagation analyzer.
        
        Args:
            max_path_length: Maximum length of propagation paths to consider
            min_probability: Minimum probability threshold for path consideration
        """
        self.max_path_length = max_path_length
        self.min_probability = min_probability
    
    def find_propagation_paths(self, cth_graph: CTHGraph, 
                             anomaly_start_node: str,
                             max_paths: int = 5) -> List[PropagationPath]:
        """
        Find most likely fault propagation paths starting from an anomalous node.
        
        Implements Algorithm 2: Find_Propagation_Path with enhancements.
        
        Args:
            cth_graph: The CTH graph to analyze
            anomaly_start_node: Starting node for propagation analysis
            max_paths: Maximum number of paths to return
        
        Returns:
            List of PropagationPath objects sorted by probability
        """
        # Find initial hyperedges containing the anomaly start node
        initial_hyperedges = cth_graph.get_hyperedges_containing(anomaly_start_node)
        
        if not initial_hyperedges:
            return []
        
        # Sort initial hyperedges by timestamp to start with earliest
        initial_hyperedges.sort(key=lambda x: x.timestamp)
        
        all_paths = []
        
        # Use BFS to explore propagation paths from each initial hyperedge
        for start_edge in initial_hyperedges:
            paths_from_edge = self._bfs_propagation_paths(cth_graph, start_edge)
            all_paths.extend(paths_from_edge)
        
        # Sort paths by probability and return top paths
        all_paths.sort(key=lambda x: x.probability, reverse=True)
        return all_paths[:max_paths]
    
    def _bfs_propagation_paths(self, cth_graph: CTHGraph, 
                              start_edge: Hyperedge) -> List[PropagationPath]:
        """
        Use BFS to find propagation paths starting from a specific hyperedge.
        """
        paths = []
        queue = deque([(start_edge, [start_edge], 1.0, {start_edge.edge_id})])
        
        while queue:
            current_edge, current_path, current_prob, visited = queue.popleft()
            
            # Check if we've reached maximum path length
            if len(current_path) >= self.max_path_length:
                if current_prob >= self.min_probability:
                    paths.append(PropagationPath(current_path, current_prob))
                continue
            
            # Find next possible hyperedges
            next_edges = cth_graph.find_next_hyperedges(current_edge, visited)
            
            if not next_edges:
                # Terminal path - add if meets probability threshold
                if current_prob >= self.min_probability:
                    paths.append(PropagationPath(current_path, current_prob))
                continue
            
            # Rank next edges by propagation probability
            ranked_next = self._rank_by_propagation_probability(current_edge, next_edges)
            
            for next_edge, transition_prob in ranked_next:
                new_prob = current_prob * transition_prob
                
                # Only continue if probability is above threshold
                if new_prob >= self.min_probability:
                    new_path = current_path + [next_edge]
                    new_visited = visited | {next_edge.edge_id}
                    queue.append((next_edge, new_path, new_prob, new_visited))
        
        return paths
    
    def _rank_by_propagation_probability(self, current_edge: Hyperedge, 
                                       next_edges: List[Hyperedge]) -> List[Tuple[Hyperedge, float]]:
        """
        Rank next hyperedges by propagation probability.
        
        This is a simplified version of what would be a trained HyperGNN model.
        Uses heuristic rules based on:
        - Time proximity
        - Node intersection strength
        - Severity correlation
        - Entity type relationships
        """
        ranked = []
        
        for next_edge in next_edges:
            prob = self._calculate_transition_probability(current_edge, next_edge)
            ranked.append((next_edge, prob))
        
        # Sort by probability (highest first)
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked
    
    def _calculate_transition_probability(self, edge1: Hyperedge, edge2: Hyperedge) -> float:
        """
        Calculate transition probability between two hyperedges.
        
        This implements a heuristic model that could be replaced with
        a trained HyperGNN model in production.
        """
        # Time proximity factor
        time_diff = (edge2.timestamp - edge1.timestamp).total_seconds()
        if time_diff <= 0:
            return 0.0
        
        # Exponential decay with time (events closer in time are more likely related)
        time_factor = math.exp(-time_diff / 300.0)  # 5-minute half-life
        
        # Node intersection factor
        intersection = edge1.get_intersection_nodes(edge2)
        intersection_strength = len(intersection) / len(edge1.nodes | edge2.nodes)
        
        # Severity escalation factor
        severity_weights = {'normal': 1, 'warning': 2, 'error': 3, 'critical': 4}
        sev1 = severity_weights.get(edge1.severity, 1)
        sev2 = severity_weights.get(edge2.severity, 1)
        
        # Prefer escalating severity
        if sev2 >= sev1:
            severity_factor = 1.0 + (sev2 - sev1) * 0.2
        else:
            severity_factor = 0.8  # Slight penalty for de-escalation
        
        # Entity type relationship factor
        entity_factor = self._calculate_entity_relationship_factor(edge1.nodes, edge2.nodes)
        
        # Combined probability
        probability = time_factor * 0.3 + intersection_strength * 0.4 + severity_factor * 0.2 + entity_factor * 0.1
        
        return min(probability, 1.0)  # Cap at 1.0
    
    def _calculate_entity_relationship_factor(self, nodes1: Set[str], nodes2: Set[str]) -> float:
        """
        Calculate relationship strength between entity sets.
        
        Higher scores for relationships like:
        - service -> pod (deployment relationship)
        - pod -> node (scheduling relationship)
        - service -> service (dependency relationship)
        """
        factor = 0.0
        
        # Extract entity types
        types1 = {node.split(':')[0] for node in nodes1 if ':' in node}
        types2 = {node.split(':')[0] for node in nodes2 if ':' in node}
        
        # Define relationship strengths
        strong_relationships = {
            ('service', 'pod'): 0.9,
            ('pod', 'node'): 0.8,
            ('service', 'service'): 0.7,
            ('pod', 'pod'): 0.6,
            ('container', 'pod'): 0.9,
            ('service', 'container'): 0.8
        }
        
        # Check for strong relationships
        for type1 in types1:
            for type2 in types2:
                if (type1, type2) in strong_relationships:
                    factor = max(factor, strong_relationships[(type1, type2)])
                elif (type2, type1) in strong_relationships:
                    factor = max(factor, strong_relationships[(type2, type1)])
        
        return factor
    
    def quantify_propagation_scope(self, paths: List[PropagationPath]) -> Dict[str, Any]:
        """
        Quantify the scope and impact of fault propagation.
        
        Implements scope quantification from CTH framework.
        
        Args:
            paths: List of propagation paths to analyze
        
        Returns:
            Dictionary containing scope analysis results
        """
        if not paths:
            return {'total_affected_nodes': 0, 'scope_summary': {}}
        
        # Collect all affected nodes across all paths
        all_affected_nodes = set()
        for path in paths:
            all_affected_nodes.update(path.total_nodes)
        
        # Analyze node types and their distribution
        node_type_distribution = defaultdict(set)
        for node in all_affected_nodes:
            if ':' in node:
                node_type, node_name = node.split(':', 1)
                node_type_distribution[node_type].add(node_name)
        
        # Calculate centrality scores for hyperedges
        centrality_scores = self._calculate_hyperedge_centrality(paths)
        
        # Identify core affected components
        core_components = self._identify_core_components(paths, centrality_scores)
        
        # Calculate temporal spread
        temporal_analysis = self._analyze_temporal_spread(paths)
        
        return {
            'total_affected_nodes': len(all_affected_nodes),
            'affected_nodes_by_type': {k: list(v) for k, v in node_type_distribution.items()},
            'node_type_counts': {k: len(v) for k, v in node_type_distribution.items()},
            'core_components': core_components,
            'centrality_scores': centrality_scores,
            'temporal_analysis': temporal_analysis,
            'scope_severity': self._calculate_scope_severity(paths),
            'propagation_velocity': self._calculate_propagation_velocity(paths)
        }
    
    def _calculate_hyperedge_centrality(self, paths: List[PropagationPath]) -> Dict[str, float]:
        """
        Calculate centrality scores for hyperedges in propagation paths.
        
        Uses a simplified version of hypergraph centrality measures.
        """
        edge_frequency = defaultdict(int)
        edge_path_positions = defaultdict(list)
        
        # Count frequency and track positions
        for path in paths:
            for i, edge in enumerate(path.hyperedges):
                edge_frequency[edge.edge_id] += 1
                edge_path_positions[edge.edge_id].append(i / len(path.hyperedges))
        
        centrality_scores = {}
        total_paths = len(paths)
        
        for edge_id, frequency in edge_frequency.items():
            # Frequency-based centrality
            frequency_score = frequency / total_paths
            
            # Position-based centrality (edges in middle of paths are more central)
            positions = edge_path_positions[edge_id]
            avg_position = sum(positions) / len(positions)
            position_score = 1.0 - abs(avg_position - 0.5) * 2  # Peak at 0.5 (middle)
            
            # Combined centrality score
            centrality_scores[edge_id] = frequency_score * 0.7 + position_score * 0.3
        
        return centrality_scores
    
    def _identify_core_components(self, paths: List[PropagationPath], 
                                centrality_scores: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Identify core components that play key roles in fault propagation.
        """
        # Get top centrality hyperedges
        sorted_edges = sorted(centrality_scores.items(), key=lambda x: x[1], reverse=True)
        top_edges = sorted_edges[:min(5, len(sorted_edges))]  # Top 5 or fewer
        
        core_components = []
        
        for edge_id, centrality in top_edges:
            # Find the hyperedge object
            edge_obj = None
            for path in paths:
                for edge in path.hyperedges:
                    if edge.edge_id == edge_id:
                        edge_obj = edge
                        break
                if edge_obj:
                    break
            
            if edge_obj:
                core_components.append({
                    'edge_id': edge_id,
                    'centrality_score': centrality,
                    'nodes': list(edge_obj.nodes),
                    'severity': edge_obj.severity,
                    'timestamp': edge_obj.timestamp.isoformat(),
                    'event_type': edge_obj.event_type
                })
        
        return core_components
    
    def _analyze_temporal_spread(self, paths: List[PropagationPath]) -> Dict[str, Any]:
        """
        Analyze temporal characteristics of fault propagation.
        """
        if not paths:
            return {}
        
        all_timestamps = []
        path_durations = []
        
        for path in paths:
            if len(path.hyperedges) >= 2:
                start_time = path.hyperedges[0].timestamp
                end_time = path.hyperedges[-1].timestamp
                duration = (end_time - start_time).total_seconds()
                path_durations.append(duration)
                
                for edge in path.hyperedges:
                    all_timestamps.append(edge.timestamp)
        
        if not all_timestamps:
            return {}
        
        earliest = min(all_timestamps)
        latest = max(all_timestamps)
        total_span = (latest - earliest).total_seconds()
        
        return {
            'earliest_event': earliest.isoformat(),
            'latest_event': latest.isoformat(),
            'total_time_span_seconds': total_span,
            'average_path_duration': sum(path_durations) / len(path_durations) if path_durations else 0,
            'max_path_duration': max(path_durations) if path_durations else 0,
            'min_path_duration': min(path_durations) if path_durations else 0
        }
    
    def _calculate_scope_severity(self, paths: List[PropagationPath]) -> str:
        """
        Calculate overall severity of the propagation scope.
        """
        severity_weights = {'normal': 1, 'warning': 2, 'error': 3, 'critical': 4}
        total_weight = 0
        total_edges = 0
        
        for path in paths:
            for edge in path.hyperedges:
                weight = severity_weights.get(edge.severity, 1)
                total_weight += weight * path.probability  # Weight by path probability
                total_edges += path.probability
        
        if total_edges == 0:
            return 'normal'
        
        avg_severity = total_weight / total_edges
        
        if avg_severity >= 3.5:
            return 'critical'
        elif avg_severity >= 2.5:
            return 'error'
        elif avg_severity >= 1.5:
            return 'warning'
        else:
            return 'normal'
    
    def _calculate_propagation_velocity(self, paths: List[PropagationPath]) -> float:
        """
        Calculate average propagation velocity (nodes affected per second).
        """
        if not paths:
            return 0.0
        
        velocities = []
        
        for path in paths:
            if len(path.hyperedges) >= 2:
                duration = (path.hyperedges[-1].timestamp - path.hyperedges[0].timestamp).total_seconds()
                if duration > 0:
                    velocity = len(path.total_nodes) / duration
                    velocities.append(velocity)
        
        return sum(velocities) / len(velocities) if velocities else 0.0
    
    def generate_propagation_report(self, cth_graph: CTHGraph, 
                                  anomaly_start_node: str) -> Dict[str, Any]:
        """
        Generate comprehensive propagation analysis report.
        
        Args:
            cth_graph: CTH graph to analyze
            anomaly_start_node: Starting node for analysis
        
        Returns:
            Complete analysis report
        """
        # Find propagation paths
        paths = self.find_propagation_paths(cth_graph, anomaly_start_node)
        
        # Quantify scope
        scope_analysis = self.quantify_propagation_scope(paths)
        
        # Generate summary
        report = {
            'analysis_timestamp': datetime.now().isoformat(),
            'anomaly_start_node': anomaly_start_node,
            'total_paths_found': len(paths),
            'propagation_paths': [path.to_dict() for path in paths],
            'scope_analysis': scope_analysis,
            'graph_statistics': cth_graph.get_statistics(),
            'recommendations': self._generate_recommendations(paths, scope_analysis)
        }
        
        return report
    
    def _generate_recommendations(self, paths: List[PropagationPath], 
                                scope_analysis: Dict[str, Any]) -> List[str]:
        """
        Generate actionable recommendations based on propagation analysis.
        """
        recommendations = []
        
        # Recommendations based on scope severity
        severity = scope_analysis.get('scope_severity', 'normal')
        if severity == 'critical':
            recommendations.append("立即启动事故响应流程，这是一个严重的系统级故障")
            recommendations.append("考虑激活灾难恢复计划")
        elif severity == 'error':
            recommendations.append("需要紧急关注，故障正在快速传播")
            recommendations.append("检查核心服务的健康状态")
        
        # Recommendations based on affected node types
        node_types = scope_analysis.get('node_type_counts', {})
        if node_types.get('service', 0) > 3:
            recommendations.append("多个服务受影响，检查服务间依赖关系")
        if node_types.get('node', 0) > 1:
            recommendations.append("多个节点受影响，可能是基础设施问题")
        
        # Recommendations based on propagation velocity
        velocity = scope_analysis.get('propagation_velocity', 0)
        if velocity > 1.0:  # More than 1 node per second
            recommendations.append("故障传播速度很快，建议立即隔离受影响组件")
        
        # Recommendations based on core components
        core_components = scope_analysis.get('core_components', [])
        if core_components:
            top_component = core_components[0]
            recommendations.append(f"重点关注核心组件: {', '.join(top_component['nodes'])}")
        
        if not recommendations:
            recommendations.append("继续监控系统状态，当前影响范围有限")
        
        return recommendations