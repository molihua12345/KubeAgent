from typing import Any, Optional
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import requests
import json
import os


class DatabaseQueryInput(BaseModel):
    """Input for database query tool."""
    application: str = Field(
        ...,
        example="default:Deployment:kafka",
        description="Application name to query data for",
    )

class DatabaseQueryTool(BaseTool):
    """Tool for querying database with application-specific parameters."""
    
    name: str = "database_query"
    description: str = """Query database for Causal-Temporal Hypergraph (CTH) data. 
    Input should include application name，do not use json format，just use str。
    Returns JSON data from the database endpoint.
    """
    args_schema: type[BaseModel] = DatabaseQueryInput
    
    def _run(
        self, 
        application: str,
        run_manager: Optional[Any] = None
    ) -> str:
        """Execute the database query."""
        try:
            # Parameters are passed directly as function arguments
            # No need to parse JSON input
            
            # Clean application parameter to remove any whitespace/newlines
            application = application.strip()

            # Construct query parameter
            key = f"cth_{application}"
            
            # Build the URL
            url = f"http://localhost:8217/db"
            
            # Make GET request with query parameter
            params = {"key": key}
            response = requests.get(url, params=params, timeout=30)
            
            # Check if request was successful
            response.raise_for_status()
            
            # Parse JSON response
            data = response.json()
            
            # Return formatted JSON string
            return json.dumps(data, indent=2, ensure_ascii=False)
            
        except requests.exceptions.RequestException as e:
            return f"Error making request to {url}: {str(e)}"
        except json.JSONDecodeError as e:
            return f"Error parsing JSON response: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"
    


def create_database_query_tool() -> DatabaseQueryTool:
    """Create and return a database query tool instance."""
    return DatabaseQueryTool()


if __name__ == "__main__":
    # Test the tool
    tool = create_database_query_tool()
    
    # Example usage
    result = tool.run(
        application="frontend",
        ip="localhost", 
        port=8080
    )
    
    print("Query result:")
    print(result)