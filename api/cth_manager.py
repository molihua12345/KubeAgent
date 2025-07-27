import threading
import time
from typing import Dict, Optional
from datetime import datetime, timedelta
from cth import CTHAgent


class CTHManager:
    """
    CTH Manager for handling multiple user sessions with thread safety.
    Provides session isolation to prevent concurrent access issues.
    """
    
    def __init__(self, session_timeout_minutes: int = 60):
        """
        Initialize CTH Manager.
        
        Args:
            session_timeout_minutes: Session timeout in minutes (default: 60)
        """
        self.user_agents: Dict[str, CTHAgent] = {}
        self.session_timestamps: Dict[str, datetime] = {}
        self.lock = threading.RLock()
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        
        # Start cleanup thread
        self._start_cleanup_thread()
    
    def get_agent(self, session_id: str) -> CTHAgent:
        """
        Get or create CTH agent for a specific session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            CTHAgent instance for the session
        """
        with self.lock:
            # Update session timestamp
            self.session_timestamps[session_id] = datetime.now()
            
            # Create new agent if not exists
            if session_id not in self.user_agents:
                self.user_agents[session_id] = CTHAgent()
            
            return self.user_agents[session_id]
    
    def remove_session(self, session_id: str) -> bool:
        """
        Remove a specific session.
        
        Args:
            session_id: Session identifier to remove
            
        Returns:
            True if session was removed, False if not found
        """
        with self.lock:
            removed = False
            if session_id in self.user_agents:
                del self.user_agents[session_id]
                removed = True
            if session_id in self.session_timestamps:
                del self.session_timestamps[session_id]
                removed = True
            return removed
    
    def clear_all_sessions(self) -> int:
        """
        Clear all sessions.
        
        Returns:
            Number of sessions cleared
        """
        with self.lock:
            count = len(self.user_agents)
            self.user_agents.clear()
            self.session_timestamps.clear()
            return count
    
    def get_session_count(self) -> int:
        """
        Get current number of active sessions.
        
        Returns:
            Number of active sessions
        """
        with self.lock:
            return len(self.user_agents)
    
    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """
        Get information about a specific session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session information dict or None if not found
        """
        with self.lock:
            if session_id not in self.user_agents:
                return None
            
            agent = self.user_agents[session_id]
            timestamp = self.session_timestamps.get(session_id)
            
            return {
                'session_id': session_id,
                'created_at': timestamp.isoformat() if timestamp else None,
                'has_cth_graph': agent.current_cth_graph is not None,
                'graph_stats': agent.current_cth_graph.get_statistics() if agent.current_cth_graph else None
            }
    
    def list_sessions(self) -> Dict[str, Dict]:
        """
        List all active sessions with their information.
        
        Returns:
            Dictionary mapping session_id to session info
        """
        with self.lock:
            sessions = {}
            for session_id in self.user_agents.keys():
                sessions[session_id] = self.get_session_info(session_id)
            return sessions
    
    def _cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        with self.lock:
            current_time = datetime.now()
            expired_sessions = []
            
            for session_id, timestamp in self.session_timestamps.items():
                if current_time - timestamp > self.session_timeout:
                    expired_sessions.append(session_id)
            
            # Remove expired sessions
            for session_id in expired_sessions:
                self.remove_session(session_id)
            
            return len(expired_sessions)
    
    def _start_cleanup_thread(self):
        """
        Start background thread for cleaning up expired sessions.
        """
        def cleanup_worker():
            while True:
                try:
                    time.sleep(300)  # Check every 5 minutes
                    cleaned = self._cleanup_expired_sessions()
                    if cleaned > 0:
                        print(f"CTH Manager: Cleaned up {cleaned} expired sessions")
                except Exception as e:
                    print(f"CTH Manager cleanup error: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()


# Global CTH manager instance
cth_manager = CTHManager()


def get_cth_manager() -> CTHManager:
    """
    Get the global CTH manager instance.
    
    Returns:
        CTHManager instance
    """
    return cth_manager