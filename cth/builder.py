"""CTH Builder Module

Implements the CTH construction algorithm that converts observability data
into Causal-Temporal Hypergraph structure.
"""

from typing import Dict, List, Any, Set, Optional
from datetime import datetime, timedelta
import json
import re
from collections import defaultdict

from .graph import CTHGraph, Hyperedge


class CTHBuilder:
    """Builder class for constructing CTH from observability data.
    
    Implements Algorithm 1 from the CTH framework:
    - Processes traces, metrics, and logs
    - Creates hyperedges based on trace correlation
    - Builds the complete CTH structure
    """
    
    def __init__(self, time_window_seconds: int = 300):
        """
        Initialize CTH builder.
        
        Args:
            time_window_seconds: Time window for event aggregation (default 5 minutes)
        """
        self.time_window = timedelta(seconds=time_window_seconds)
        self.anomaly_keywords = {
            'error', 'exception', 'failed', 'timeout', 'refused', 'denied',
            'unavailable', 'unreachable', 'critical', 'fatal', 'panic',
            'warning', 'alert', 'threshold', 'limit', 'exceeded'
        }
        
    def build_cth_from_json(self, data: Dict[str, Any]) -> CTHGraph:
        """
        Build CTH graph from JSON observability data.
        
        Expected JSON format:
        {
            "traces": [
                {
                    "trace_id": "abc123",
                    "spans": [
                        {
                            "service": "service-a",
                            "operation": "get-user",
                            "start_time": "2024-01-01T10:00:00Z",
                            "end_time": "2024-01-01T10:00:01Z",
                            "status": "error",
                            "tags": {"pod": "pod-123", "node": "node-1"}
                        }
                    ]
                }
            ],
            "metrics": [
                {
                    "entity": "service-a",
                    "metric_name": "cpu_usage",
                    "value": 95.5,
                    "timestamp": "2024-01-01T10:00:00Z",
                    "is_anomalous": true,
                    "tags": {"pod": "pod-123"}
                }
            ],
            "logs": [
                {
                    "entity": "service-a",
                    "message": "Connection timeout to database",
                    "level": "error",
                    "timestamp": "2024-01-01T10:00:00Z",
                    "tags": {"pod": "pod-123"}
                }
            ]
        }
        """
        cth_graph = CTHGraph()
        
        traces = data.get('traces', [])
        metrics = data.get('metrics', [])
        logs = data.get('logs', [])
        
        # Process each trace to create hyperedges
        for trace in traces:
            hyperedge = self._create_hyperedge_from_trace(trace, metrics, logs)
            if hyperedge:
                cth_graph.add_hyperedge(hyperedge)
        
        # Also create hyperedges for orphaned anomalous events
        # (events not associated with any trace)
        orphaned_hyperedges = self._create_orphaned_hyperedges(traces, metrics, logs)
        for hyperedge in orphaned_hyperedges:
            cth_graph.add_hyperedge(hyperedge)
        
        return cth_graph
    
    def _create_hyperedge_from_trace(self, trace: Dict[str, Any], 
                                   metrics: List[Dict[str, Any]], 
                                   logs: List[Dict[str, Any]]) -> Optional[Hyperedge]:
        """
        Create a hyperedge from a single trace and associated observability data.
        
        Implements the core logic of Algorithm 1: Build_CTH
        """
        trace_id = trace.get('trace_id')
        spans = trace.get('spans', [])
        
        if not spans:
            return None
        
        # Extract entities (nodes) from trace spans
        nodes = set()
        trace_start_time = None
        trace_end_time = None
        has_errors = False
        
        for span in spans:
            # Add service as node
            service = span.get('service')
            if service:
                nodes.add(f"service:{service}")
            
            # Add pod/container as node if available
            tags = span.get('tags', {})
            if 'pod' in tags:
                nodes.add(f"pod:{tags['pod']}")
            if 'container' in tags:
                nodes.add(f"container:{tags['container']}")
            if 'node' in tags:
                nodes.add(f"node:{tags['node']}")
            
            # Track time range
            start_time = self._parse_timestamp(span.get('start_time'))
            end_time = self._parse_timestamp(span.get('end_time'))
            
            if start_time:
                if trace_start_time is None or start_time < trace_start_time:
                    trace_start_time = start_time
            if end_time:
                if trace_end_time is None or end_time > trace_end_time:
                    trace_end_time = end_time
            
            # Check for errors
            if span.get('status') in ['error', 'failed', 'timeout']:
                has_errors = True
        
        if not nodes or not trace_start_time:
            return None
        
        # Find anomalous metrics within trace time window
        anomalous_metrics = self._find_anomalous_metrics(
            metrics, nodes, trace_start_time, trace_end_time or trace_start_time
        )
        
        # Find critical logs within trace time window  
        critical_logs = self._find_critical_logs(
            logs, nodes, trace_start_time, trace_end_time or trace_start_time
        )
        
        # Only create hyperedge if there are anomalies or errors
        if not (anomalous_metrics or critical_logs or has_errors):
            return None
        
        # Determine event severity
        severity = self._determine_severity(spans, anomalous_metrics, critical_logs)
        
        # Calculate duration
        duration = None
        if trace_end_time and trace_start_time:
            duration = (trace_end_time - trace_start_time).total_seconds()
        
        return Hyperedge(
            nodes=nodes,
            metrics=set(anomalous_metrics),
            logs=set(critical_logs),
            timestamp=trace_start_time,
            trace_id=trace_id,
            event_type="trace_event",
            severity=severity,
            duration=duration
        )
    
    def _create_orphaned_hyperedges(self, traces: List[Dict[str, Any]],
                                   metrics: List[Dict[str, Any]], 
                                   logs: List[Dict[str, Any]]) -> List[Hyperedge]:
        """
        Create hyperedges for anomalous events not associated with any trace.
        """
        orphaned_hyperedges = []
        
        # Get all trace IDs and time ranges
        trace_coverage = set()
        for trace in traces:
            trace_id = trace.get('trace_id')
            if trace_id:
                trace_coverage.add(trace_id)
        
        # Group orphaned anomalous metrics by time windows
        orphaned_metrics = [m for m in metrics 
                          if m.get('is_anomalous', False) and 
                          m.get('trace_id') not in trace_coverage]
        
        orphaned_logs = [l for l in logs 
                        if self._is_critical_log(l) and 
                        l.get('trace_id') not in trace_coverage]
        
        # Group by time windows
        time_groups = self._group_by_time_windows(orphaned_metrics + orphaned_logs)
        
        for time_window, events in time_groups.items():
            nodes = set()
            metrics_set = set()
            logs_set = set()
            
            for event in events:
                entity = event.get('entity')
                if entity:
                    # Infer entity type
                    if 'service' in entity.lower():
                        nodes.add(f"service:{entity}")
                    elif 'pod' in entity.lower():
                        nodes.add(f"pod:{entity}")
                    else:
                        nodes.add(f"entity:{entity}")
                
                if 'metric_name' in event:  # It's a metric
                    metrics_set.add(f"{entity}:{event['metric_name']}")
                else:  # It's a log
                    logs_set.add(event.get('message', '')[:100])  # Truncate long messages
            
            if nodes and (metrics_set or logs_set):
                hyperedge = Hyperedge(
                    nodes=nodes,
                    metrics=metrics_set,
                    logs=logs_set,
                    timestamp=time_window,
                    event_type="orphaned_anomaly",
                    severity="warning"
                )
                orphaned_hyperedges.append(hyperedge)
        
        return orphaned_hyperedges
    
    def _find_anomalous_metrics(self, metrics: List[Dict[str, Any]], 
                              nodes: Set[str], start_time: datetime, 
                              end_time: datetime) -> List[str]:
        """
        Find anomalous metrics associated with nodes within time window.
        """
        anomalous = []
        
        for metric in metrics:
            if not metric.get('is_anomalous', False):
                continue
            
            metric_time = self._parse_timestamp(metric.get('timestamp'))
            if not metric_time or not (start_time <= metric_time <= end_time + self.time_window):
                continue
            
            entity = metric.get('entity', '')
            metric_name = metric.get('metric_name', '')
            
            # Check if metric is associated with any of the nodes
            for node in nodes:
                if entity in node or any(tag in node for tag in metric.get('tags', {}).values()):
                    anomalous.append(f"{entity}:{metric_name}")
                    break
        
        return anomalous
    
    def _find_critical_logs(self, logs: List[Dict[str, Any]], 
                          nodes: Set[str], start_time: datetime, 
                          end_time: datetime) -> List[str]:
        """
        Find critical log events associated with nodes within time window.
        """
        critical = []
        
        for log in logs:
            if not self._is_critical_log(log):
                continue
            
            log_time = self._parse_timestamp(log.get('timestamp'))
            if not log_time or not (start_time <= log_time <= end_time + self.time_window):
                continue
            
            entity = log.get('entity', '')
            
            # Check if log is associated with any of the nodes
            for node in nodes:
                if entity in node or any(tag in node for tag in log.get('tags', {}).values()):
                    message = log.get('message', '')[:100]  # Truncate long messages
                    critical.append(message)
                    break
        
        return critical
    
    def _is_critical_log(self, log: Dict[str, Any]) -> bool:
        """
        Determine if a log entry is critical based on level and content.
        """
        level = log.get('level', '').lower()
        if level in ['error', 'critical', 'fatal', 'panic']:
            return True
        
        message = log.get('message', '').lower()
        return any(keyword in message for keyword in self.anomaly_keywords)
    
    def _determine_severity(self, spans: List[Dict[str, Any]], 
                          metrics: List[str], logs: List[str]) -> str:
        """
        Determine overall severity of the hyperedge event.
        """
        # Check span statuses
        for span in spans:
            if span.get('status') in ['critical', 'fatal']:
                return 'critical'
            elif span.get('status') == 'error':
                return 'error'
        
        # Check log content for severity indicators
        for log in logs:
            log_lower = log.lower()
            if any(word in log_lower for word in ['critical', 'fatal', 'panic']):
                return 'critical'
            elif any(word in log_lower for word in ['error', 'exception', 'failed']):
                return 'error'
        
        # If we have anomalous metrics or any logs, it's at least a warning
        if metrics or logs:
            return 'warning'
        
        return 'normal'
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """
        Parse timestamp string to datetime object.
        """
        if not timestamp_str:
            return None
        
        try:
            # Try ISO format first
            if 'T' in timestamp_str:
                return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                # Try other common formats
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f']:
                    try:
                        return datetime.strptime(timestamp_str, fmt)
                    except ValueError:
                        continue
        except Exception:
            pass
        
        return None
    
    def _group_by_time_windows(self, events: List[Dict[str, Any]]) -> Dict[datetime, List[Dict[str, Any]]]:
        """
        Group events by time windows for orphaned event processing.
        """
        groups = defaultdict(list)
        
        for event in events:
            timestamp = self._parse_timestamp(event.get('timestamp'))
            if timestamp:
                # Round to time window boundary
                window_start = timestamp.replace(second=0, microsecond=0)
                window_start = window_start.replace(minute=(window_start.minute // 5) * 5)
                groups[window_start].append(event)
        
        return dict(groups)
    
    def validate_input_data(self, data: Dict[str, Any]) -> List[str]:
        """
        Validate input JSON data format and return list of validation errors.
        """
        errors = []
        
        if not isinstance(data, dict):
            errors.append("Input data must be a dictionary")
            return errors
        
        # Check required top-level keys
        required_keys = ['traces', 'metrics', 'logs']
        for key in required_keys:
            if key not in data:
                errors.append(f"Missing required key: {key}")
            elif not isinstance(data[key], list):
                errors.append(f"Key '{key}' must be a list")
        
        # Validate traces structure
        traces = data.get('traces', [])
        for i, trace in enumerate(traces):
            if not isinstance(trace, dict):
                errors.append(f"Trace {i} must be a dictionary")
                continue
            
            if 'trace_id' not in trace:
                errors.append(f"Trace {i} missing trace_id")
            
            if 'spans' not in trace or not isinstance(trace['spans'], list):
                errors.append(f"Trace {i} must have 'spans' as a list")
        
        # Validate metrics structure
        metrics = data.get('metrics', [])
        for i, metric in enumerate(metrics):
            if not isinstance(metric, dict):
                errors.append(f"Metric {i} must be a dictionary")
                continue
            
            required_metric_keys = ['entity', 'metric_name', 'timestamp']
            for key in required_metric_keys:
                if key not in metric:
                    errors.append(f"Metric {i} missing required key: {key}")
        
        # Validate logs structure
        logs = data.get('logs', [])
        for i, log in enumerate(logs):
            if not isinstance(log, dict):
                errors.append(f"Log {i} must be a dictionary")
                continue
            
            required_log_keys = ['entity', 'message', 'timestamp']
            for key in required_log_keys:
                if key not in log:
                    errors.append(f"Log {i} missing required key: {key}")
        
        return errors