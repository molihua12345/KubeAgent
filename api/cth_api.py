"""CTH API Module

Provides REST API endpoints for CTH (Causal-Temporal Hypergraph) functionality.
Allows external systems to send observability data and receive CTH analysis results.
"""

from flask import Blueprint, request, jsonify
from typing import Dict, Any
import json
import traceback
import uuid
from datetime import datetime

from cth import CTHAgent, CTHBuilder, PropagationAnalyzer
from .cth_manager import get_cth_manager

# Create Blueprint for CTH API
cth_api = Blueprint('cth_api', __name__, url_prefix='/api/cth')

# Global CTH manager instance
cth_manager = get_cth_manager()

def init_cth_api(agent_instance=None):
    """Initialize CTH API with manager."""
    global cth_manager
    cth_manager = get_cth_manager()
    print("CTH API initialized with session isolation support")


def get_session_id_from_request() -> str:
    """Extract or generate session ID from request."""
    # Try to get session_id from headers first
    session_id = request.headers.get('X-Session-ID')
    
    # Try to get from JSON body
    if not session_id and request.is_json:
        data = request.get_json()
        if data:
            session_id = data.get('session_id')
    
    # Try to get from query parameters
    if not session_id:
        session_id = request.args.get('session_id')
    
    # Generate new session ID if not provided
    if not session_id:
        session_id = str(uuid.uuid4())
    
    return session_id


@cth_api.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for CTH API."""
    session_count = cth_manager.get_session_count()
    return jsonify({
        'status': 'healthy',
        'service': 'CTH API',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0',
        'session_isolation': True,
        'active_sessions': session_count
    })


@cth_api.route('/build', methods=['POST'])
def build_cth_graph():
    """
    Build CTH graph from observability data.
    
    Expected JSON payload:
    {
        "session_id": "optional-session-id",
        "traces": [...],
        "metrics": [...],
        "logs": [...]
    }
    
    Returns:
    {
        "success": true/false,
        "message": "...",
        "session_id": "...",
        "cth_graph": {...},
        "statistics": {...},
        "errors": [...]
    }
    """
    try:
        # Validate request
        if not request.is_json:
            return jsonify({
                'success': False,
                'message': 'Request must be JSON',
                'errors': ['Content-Type must be application/json']
            }), 400
        
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'Empty JSON payload',
                'errors': ['Request body cannot be empty']
            }), 400
        
        # Get session ID and CTH agent for this session
        session_id = get_session_id_from_request()
        cth_agent = cth_manager.get_agent(session_id)
        
        # Build CTH graph
        result = cth_agent.build_cth_from_data(data)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'CTH graph built successfully',
                'session_id': session_id,
                'cth_graph': result['cth_graph'],
                'statistics': result['statistics'],
                'errors': []
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to build CTH graph',
                'session_id': session_id,
                'cth_graph': None,
                'statistics': None,
                'errors': result['errors']
            }), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Internal server error: {str(e)}',
            'session_id': get_session_id_from_request() if 'get_session_id_from_request' in locals() else 'unknown',
            'cth_graph': None,
            'statistics': None,
            'errors': [str(e), traceback.format_exc()]
        }), 500


@cth_api.route('/analyze', methods=['POST'])
def analyze_fault():
    """
    Perform fault analysis using CTH.
    
    Expected JSON payload:
    {
        "session_id": "optional-session-id",
        "alert_info": "Service checkout experiencing high latency",
        "anomaly_node": "service:checkout" (optional)
    }
    
    Returns:
    {
        "success": true/false,
        "message": "...",
        "session_id": "...",
        "analysis_result": "...",
        "propagation_paths": [...],
        "scope_analysis": {...},
        "recommendations": [...]
    }
    """
    try:
        # Validate request
        if not request.is_json:
            return jsonify({
                'success': False,
                'message': 'Request must be JSON'
            }), 400
        
        data = request.get_json()
        alert_info = data.get('alert_info', '')
        
        if not alert_info:
            return jsonify({
                'success': False,
                'message': 'alert_info is required'
            }), 400
        
        # Get session ID and CTH agent for this session
        session_id = get_session_id_from_request()
        cth_agent = cth_manager.get_agent(session_id)
        
        # Check if CTH graph exists
        if not cth_agent.current_cth_graph:
            return jsonify({
                'success': False,
                'message': 'No CTH graph available. Please build CTH graph first using /api/cth/build endpoint.',
                'session_id': session_id
            }), 400
        
        # Perform analysis
        analysis_steps = []
        final_result = None
        
        for step in cth_agent.interactive_diagnosis(alert_info):
            if isinstance(step, str):
                analysis_steps.append(step)
            else:
                final_result = step
        
        # Get propagation paths for additional context
        anomaly_nodes = cth_agent._extract_anomaly_nodes_from_alert(alert_info)
        all_paths = []
        for node in anomaly_nodes:
            paths = cth_agent.propagation_analyzer.find_propagation_paths(
                cth_agent.current_cth_graph, node
            )
            all_paths.extend(paths)
        
        # Get scope analysis
        scope_analysis = {}
        recommendations = []
        if all_paths:
            scope_analysis = cth_agent.propagation_analyzer.quantify_propagation_scope(all_paths)
            recommendations = cth_agent.propagation_analyzer._generate_recommendations(all_paths, scope_analysis)
        
        return jsonify({
            'success': True,
            'message': 'Analysis completed successfully',
            'session_id': session_id,
            'analysis_result': final_result or '\n'.join(analysis_steps),
            'analysis_steps': analysis_steps,
            'propagation_paths': [path.to_dict() for path in all_paths],
            'scope_analysis': scope_analysis,
            'recommendations': recommendations,
            'anomaly_nodes': anomaly_nodes
        }), 200
    
    except Exception as e:
        session_id = get_session_id_from_request() if 'get_session_id_from_request' in locals() else 'unknown'
        return jsonify({
            'success': False,
            'message': f'Analysis failed: {str(e)}',
            'session_id': session_id,
            'error_details': traceback.format_exc()
        }), 500


@cth_api.route('/query', methods=['POST'])
def query_cth_graph():
    """
    Query CTH graph for specific information.
    
    Expected JSON payload:
    {
        "session_id": "optional-session-id",
        "query_type": "query_nodes_by_entity|query_anomalous_events|find_propagation_paths|get_graph_statistics",
        "entity_name": "service:checkout" (optional),
        "start_node": "service:checkout" (optional),
        "severity_level": "error" (optional),
        "max_paths": 5 (optional)
    }
    
    Returns:
    {
        "success": true/false,
        "message": "...",
        "session_id": "...",
        "query_result": {...}
    }
    """
    try:
        # Validate request
        if not request.is_json:
            return jsonify({
                'success': False,
                'message': 'Request must be JSON'
            }), 400
        
        data = request.get_json()
        query_type = data.get('query_type', '')
        
        if not query_type:
            return jsonify({
                'success': False,
                'message': 'query_type is required'
            }), 400
        
        # Get session ID and CTH agent for this session
        session_id = get_session_id_from_request()
        cth_agent = cth_manager.get_agent(session_id)
        
        # Check if CTH graph exists
        if not cth_agent.current_cth_graph:
            return jsonify({
                'success': False,
                'message': 'No CTH graph available. Please build CTH graph first.',
                'session_id': session_id
            }), 400
        
        # Prepare query parameters
        kwargs = {}
        for key in ['entity_name', 'start_node', 'severity_level', 'max_paths']:
            if key in data:
                kwargs[key] = data[key]
        
        # Execute query
        result = cth_agent.query_cth_graph(query_type, **kwargs)
        
        if 'error' in result:
            return jsonify({
                'success': False,
                'message': f'Query failed: {result["error"]}',
                'session_id': session_id
            }), 400
        
        return jsonify({
            'success': True,
            'message': 'Query executed successfully',
            'session_id': session_id,
            'query_result': result
        }), 200
    
    except Exception as e:
        session_id = get_session_id_from_request() if 'get_session_id_from_request' in locals() else 'unknown'
        return jsonify({
            'success': False,
            'message': f'Query failed: {str(e)}',
            'session_id': session_id,
            'error_details': traceback.format_exc()
        }), 500


@cth_api.route('/remediation', methods=['POST'])
def generate_remediation():
    """
    Generate remediation plan based on analysis results.
    
    Expected JSON payload:
    {
        "session_id": "optional-session-id",
        "alert_info": "Service checkout experiencing high latency",
        "analysis_result": "..." (optional, will perform analysis if not provided)
    }
    
    Returns:
    {
        "success": true/false,
        "message": "...",
        "session_id": "...",
        "remediation_plan": "..."
    }
    """
    try:
        # Validate request
        if not request.is_json:
            return jsonify({
                'success': False,
                'message': 'Request must be JSON'
            }), 400
        
        data = request.get_json()
        alert_info = data.get('alert_info', '')
        analysis_result = data.get('analysis_result', '')
        
        if not alert_info:
            return jsonify({
                'success': False,
                'message': 'alert_info is required'
            }), 400
        
        # Get session ID and CTH agent for this session
        session_id = get_session_id_from_request()
        cth_agent = cth_manager.get_agent(session_id)
        
        # Check if CTH graph exists
        if not cth_agent.current_cth_graph:
            return jsonify({
                'success': False,
                'message': 'No CTH graph available. Please build CTH graph first.',
                'session_id': session_id
            }), 400
        
        # If no analysis result provided, perform quick analysis
        if not analysis_result:
            analysis_result = f"Quick analysis for: {alert_info}"
        
        # Get propagation paths and scope analysis
        anomaly_nodes = cth_agent._extract_anomaly_nodes_from_alert(alert_info)
        all_paths = []
        for node in anomaly_nodes:
            paths = cth_agent.propagation_analyzer.find_propagation_paths(
                cth_agent.current_cth_graph, node
            )
            all_paths.extend(paths)
        
        if not all_paths:
            return jsonify({
                'success': False,
                'message': 'No propagation paths found. Cannot generate remediation plan.',
                'session_id': session_id
            }), 400
        
        scope_analysis = cth_agent.propagation_analyzer.quantify_propagation_scope(all_paths)
        
        # Generate remediation plan
        remediation_plan = cth_agent.generate_remediation_plan(
            analysis_result, all_paths, scope_analysis
        )
        
        return jsonify({
            'success': True,
            'message': 'Remediation plan generated successfully',
            'session_id': session_id,
            'remediation_plan': remediation_plan,
            'scope_analysis': scope_analysis
        }), 200
    
    except Exception as e:
        session_id = get_session_id_from_request() if 'get_session_id_from_request' in locals() else 'unknown'
        return jsonify({
            'success': False,
            'message': f'Remediation generation failed: {str(e)}',
            'session_id': session_id,
            'error_details': traceback.format_exc()
        }), 500


@cth_api.route('/status', methods=['GET'])
def get_cth_status():
    """
    Get current CTH system status for a specific session.
    
    Query parameters or headers:
    - session_id: Session identifier (optional)
    
    Returns:
    {
        "session_id": "...",
        "cth_graph_available": true/false,
        "graph_statistics": {...},
        "agent_status": "ready|not_initialized",
        "session_info": {...}
    }
    """
    try:
        # Get session ID and CTH agent for this session
        session_id = get_session_id_from_request()
        cth_agent = cth_manager.get_agent(session_id)
        
        graph_available = cth_agent.current_cth_graph is not None
        statistics = None
        
        if graph_available:
            statistics = cth_agent.current_cth_graph.get_statistics()
        
        # Get session information
        session_info = cth_manager.get_session_info(session_id)
        
        return jsonify({
            'session_id': session_id,
            'cth_graph_available': graph_available,
            'graph_statistics': statistics,
            'agent_status': 'ready',
            'session_info': session_info
        })
    
    except Exception as e:
        return jsonify({
            'cth_graph_available': False,
            'graph_statistics': None,
            'agent_status': 'error',
            'error': str(e)
        }), 500


@cth_api.route('/clear', methods=['POST'])
def clear_cth_graph():
    """
    Clear current CTH graph data for a specific session.
    
    Expected JSON payload (optional):
    {
        "session_id": "optional-session-id"
    }
    
    Returns:
    {
        "success": true/false,
        "message": "...",
        "session_id": "..."
    }
    """
    try:
        # Get session ID and CTH agent for this session
        session_id = get_session_id_from_request()
        cth_agent = cth_manager.get_agent(session_id)
        
        if cth_agent.current_cth_graph:
            cth_agent.current_cth_graph.clear()
            cth_agent.current_cth_graph = None
        
        return jsonify({
            'success': True,
            'message': 'CTH graph cleared successfully',
            'session_id': session_id
        })
    
    except Exception as e:
        session_id = get_session_id_from_request() if 'get_session_id_from_request' in locals() else 'unknown'
        return jsonify({
            'success': False,
            'message': f'Failed to clear CTH graph: {str(e)}',
            'session_id': session_id
        }), 500


@cth_api.route('/sessions', methods=['GET'])
def list_sessions():
    """
    List all active CTH sessions (admin endpoint).
    
    Returns:
    {
        "success": true,
        "sessions": {...},
        "total_sessions": 5
    }
    """
    try:
        sessions = cth_manager.list_sessions()
        return jsonify({
            'success': True,
            'sessions': sessions,
            'total_sessions': len(sessions)
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to list sessions: {str(e)}'
        }), 500


@cth_api.route('/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """
    Delete a specific CTH session (admin endpoint).
    
    Returns:
    {
        "success": true/false,
        "message": "...",
        "session_id": "..."
    }
    """
    try:
        removed = cth_manager.remove_session(session_id)
        
        if removed:
            return jsonify({
                'success': True,
                'message': f'Session {session_id} deleted successfully',
                'session_id': session_id
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Session {session_id} not found',
                'session_id': session_id
            }), 404
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to delete session: {str(e)}',
            'session_id': session_id
        }), 500


@cth_api.route('/sessions/clear-all', methods=['POST'])
def clear_all_sessions():
    """
    Clear all CTH sessions (admin endpoint).
    
    Returns:
    {
        "success": true,
        "message": "...",
        "cleared_sessions": 5
    }
    """
    try:
        cleared_count = cth_manager.clear_all_sessions()
        
        return jsonify({
            'success': True,
            'message': f'All sessions cleared successfully',
            'cleared_sessions': cleared_count
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Failed to clear all sessions: {str(e)}'
        }), 500