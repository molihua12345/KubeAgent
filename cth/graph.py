"""CTH Graph Core Data Structures

Implements the core data structures for Causal-Temporal Hypergraph:
- Hyperedge: represents a multi-entity concurrent event
- CTHGraph: the main hypergraph structure
"""

from typing import Set, List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
import networkx as nx


@dataclass
class Hyperedge:
    """Represents a hyperedge in CTH framework.
    
    A hyperedge h = (N, M, L, T) where:
    - N: set of nodes (entities) involved in the same business event
    - M: set of anomalous metrics associated with nodes in N
    - L: set of critical log events associated with nodes in N  
    - T: timestamp or time window of the event
    """
    
    # Core components of hyperedge
    nodes: Set[str] = field(default_factory=set)
    metrics: Set[str] = field(default_factory=set)
    logs: Set[str] = field(default_factory=set)
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Additional metadata
    trace_id: Optional[str] = None
    event_type: str = "unknown"
    severity: str = "normal"  # normal, warning, error, critical
    duration: Optional[float] = None  # event duration in seconds
    
    # Unique identifier
    edge_id: str = field(default="")
    
    def __post_init__(self):
        if not self.edge_id:
            # Generate unique edge ID based on content
            content = f"{sorted(self.nodes)}_{self.timestamp.isoformat()}"
            self.edge_id = f"edge_{hash(content) % 1000000}"
    
    def has_intersection(self, other: 'Hyperedge') -> bool:
        """Check if this hyperedge has node intersection with another."""
        return bool(self.nodes & other.nodes)
    
    def get_intersection_nodes(self, other: 'Hyperedge') -> Set[str]:
        """Get intersection nodes with another hyperedge."""
        return self.nodes & other.nodes
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert hyperedge to dictionary representation."""
        return {
            'edge_id': self.edge_id,
            'nodes': list(self.nodes),
            'metrics': list(self.metrics),
            'logs': list(self.logs),
            'timestamp': self.timestamp.isoformat(),
            'trace_id': self.trace_id,
            'event_type': self.event_type,
            'severity': self.severity,
            'duration': self.duration
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Hyperedge':
        """Create hyperedge from dictionary representation."""
        return cls(
            nodes=set(data.get('nodes', [])),
            metrics=set(data.get('metrics', [])),
            logs=set(data.get('logs', [])),
            timestamp=datetime.fromisoformat(data.get('timestamp', datetime.now().isoformat())),
            trace_id=data.get('trace_id'),
            event_type=data.get('event_type', 'unknown'),
            severity=data.get('severity', 'normal'),
            duration=data.get('duration'),
            edge_id=data.get('edge_id', '')
        )


class CTHGraph:
    """Causal-Temporal Hypergraph for cloud-native system analysis.
    
    This class implements the core CTH data structure that maintains:
    - A collection of hyperedges representing concurrent events
    - Temporal ordering of events
    - Node-to-hyperedge mappings for efficient querying
    """
    
    def __init__(self):
        self.hyperedges: Dict[str, Hyperedge] = {}
        self.node_to_edges: Dict[str, Set[str]] = {}  # node -> set of edge_ids
        self.time_ordered_edges: List[str] = []  # edge_ids ordered by time
        self.metadata: Dict[str, Any] = {
            'created_at': datetime.now(),
            'version': '1.0',
            'total_events': 0
        }
    
    def add_hyperedge(self, hyperedge: Hyperedge) -> None:
        """Add a hyperedge to the graph."""
        edge_id = hyperedge.edge_id
        
        # Add to main storage
        self.hyperedges[edge_id] = hyperedge
        
        # Update node-to-edge mappings
        for node in hyperedge.nodes:
            if node not in self.node_to_edges:
                self.node_to_edges[node] = set()
            self.node_to_edges[node].add(edge_id)
        
        # Insert into time-ordered list (maintain temporal order)
        self._insert_edge_by_time(edge_id)
        
        # Update metadata
        self.metadata['total_events'] += 1
        self.metadata['last_updated'] = datetime.now()
    
    def _insert_edge_by_time(self, edge_id: str) -> None:
        """Insert edge into time-ordered list maintaining chronological order."""
        edge = self.hyperedges[edge_id]
        
        # Binary search for insertion point
        left, right = 0, len(self.time_ordered_edges)
        while left < right:
            mid = (left + right) // 2
            mid_edge = self.hyperedges[self.time_ordered_edges[mid]]
            if mid_edge.timestamp <= edge.timestamp:
                left = mid + 1
            else:
                right = mid
        
        self.time_ordered_edges.insert(left, edge_id)
    
    def get_hyperedges_containing(self, node: str) -> List[Hyperedge]:
        """Get all hyperedges containing a specific node."""
        if node not in self.node_to_edges:
            return []
        
        return [self.hyperedges[edge_id] for edge_id in self.node_to_edges[node]]
    
    def get_hyperedges_in_timerange(self, start_time: datetime, end_time: datetime) -> List[Hyperedge]:
        """Get all hyperedges within a time range."""
        result = []
        for edge_id in self.time_ordered_edges:
            edge = self.hyperedges[edge_id]
            if start_time <= edge.timestamp <= end_time:
                result.append(edge)
            elif edge.timestamp > end_time:
                break  # Since edges are time-ordered, we can break early
        return result
    
    def find_next_hyperedges(self, current_edge: Hyperedge, visited: Set[str] = None) -> List[Hyperedge]:
        """Find potential next hyperedges in propagation path.
        
        Returns hyperedges that:
        1. Occur after the current edge in time
        2. Have node intersection with current edge
        3. Haven't been visited yet
        """
        if visited is None:
            visited = set()
        
        candidates = []
        current_time = current_edge.timestamp
        
        # Look for edges that come after current edge
        for edge_id in self.time_ordered_edges:
            if edge_id in visited or edge_id == current_edge.edge_id:
                continue
                
            edge = self.hyperedges[edge_id]
            
            # Must be after current edge in time
            if edge.timestamp <= current_time:
                continue
            
            # Must have node intersection (propagation condition)
            if current_edge.has_intersection(edge):
                candidates.append(edge)
        
        return candidates
    
    def get_propagation_graph(self) -> nx.DiGraph:
        """Convert CTH to NetworkX directed graph for analysis.
        
        Creates a directed graph where:
        - Nodes are hyperedge IDs
        - Edges represent potential propagation paths
        - Edge weights represent propagation probability/strength
        """
        G = nx.DiGraph()
        
        # Add all hyperedges as nodes
        for edge_id, hyperedge in self.hyperedges.items():
            G.add_node(edge_id, **hyperedge.to_dict())
        
        # Add directed edges for potential propagation paths
        for edge_id, hyperedge in self.hyperedges.items():
            next_edges = self.find_next_hyperedges(hyperedge)
            for next_edge in next_edges:
                # Calculate propagation weight based on:
                # 1. Time proximity
                # 2. Node intersection size
                # 3. Severity correlation
                weight = self._calculate_propagation_weight(hyperedge, next_edge)
                G.add_edge(edge_id, next_edge.edge_id, weight=weight)
        
        return G
    
    def _calculate_propagation_weight(self, edge1: Hyperedge, edge2: Hyperedge) -> float:
        """Calculate propagation weight between two hyperedges."""
        # Time proximity factor (closer in time = higher weight)
        time_diff = (edge2.timestamp - edge1.timestamp).total_seconds()
        time_factor = 1.0 / (1.0 + time_diff / 60.0)  # Decay over minutes
        
        # Node intersection factor
        intersection_size = len(edge1.get_intersection_nodes(edge2))
        total_nodes = len(edge1.nodes | edge2.nodes)
        intersection_factor = intersection_size / total_nodes if total_nodes > 0 else 0
        
        # Severity correlation factor
        severity_weights = {'normal': 1, 'warning': 2, 'error': 3, 'critical': 4}
        sev1 = severity_weights.get(edge1.severity, 1)
        sev2 = severity_weights.get(edge2.severity, 1)
        severity_factor = min(sev1, sev2) / max(sev1, sev2) if max(sev1, sev2) > 0 else 0
        
        # Combined weight
        return time_factor * 0.4 + intersection_factor * 0.4 + severity_factor * 0.2
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics."""
        if not self.hyperedges:
            return {'total_edges': 0, 'total_nodes': 0, 'time_span': 0}
        
        all_nodes = set()
        for edge in self.hyperedges.values():
            all_nodes.update(edge.nodes)
        
        timestamps = [edge.timestamp for edge in self.hyperedges.values()]
        time_span = (max(timestamps) - min(timestamps)).total_seconds() if len(timestamps) > 1 else 0
        
        # Convert metadata datetime objects to ISO format strings for JSON serialization
        serializable_metadata = {}
        for key, value in self.metadata.items():
            if isinstance(value, datetime):
                serializable_metadata[key] = value.isoformat()
            else:
                serializable_metadata[key] = value
        
        return {
            'total_edges': len(self.hyperedges),
            'total_nodes': len(all_nodes),
            'time_span_seconds': time_span,
            'earliest_event': min(timestamps).isoformat() if timestamps else None,
            'latest_event': max(timestamps).isoformat() if timestamps else None,
            **serializable_metadata
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entire graph to dictionary representation."""
        return {
            'hyperedges': {eid: edge.to_dict() for eid, edge in self.hyperedges.items()},
            'metadata': self.metadata,
            'statistics': self.get_statistics()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CTHGraph':
        """Create CTH graph from dictionary representation."""
        graph = cls()
        graph.metadata = data.get('metadata', {})
        
        # Reconstruct hyperedges
        hyperedges_data = data.get('hyperedges', {})
        for edge_id, edge_data in hyperedges_data.items():
            hyperedge = Hyperedge.from_dict(edge_data)
            graph.add_hyperedge(hyperedge)
        
        return graph
    
    def clear(self) -> None:
        """Clear all data from the graph."""
        self.hyperedges.clear()
        self.node_to_edges.clear()
        self.time_ordered_edges.clear()
        self.metadata = {
            'created_at': datetime.now(),
            'version': '1.0',
            'total_events': 0
        }