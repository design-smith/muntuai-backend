import os
from dotenv import load_dotenv
import autogen
from typing import Dict, List, Any, Optional
import json
from backend.GraphRAG.graphrag.engine.context_builder import GraphRAGContextBuilder

# Load environment variables
load_dotenv()

class SearchAgent:
    def __init__(self, context_builder: Optional[GraphRAGContextBuilder] = None):
        """Initialize the search agent with a context builder."""
        self.context_builder = context_builder
        
        # Configure the DeepSeek API
        config_list = [
            {
                "model": "deepseek-chat",
                "api_key": os.getenv("DEEPSEEK_API_KEY"),
                "base_url": "https://api.deepseek.com/v1"
            }
        ]

        # Create the agent
        self.agent = autogen.UserProxyAgent(
            name="SearchAgent",
            system_message="""You are a specialized search agent that analyzes and searches through data sources.
Your job is to:
1. Take raw results from various sources
2. Break them down into meaningful chunks
3. Perform semantic search on these chunks
4. Determine which chunks are relevant to the query
5. Return the most relevant information

You have access to multiple search methods:
1. Semantic Search: Understand the meaning behind queries and content
2. Keyword Search: Find exact matches and related terms
3. Contextual Search: Consider relationships between pieces of information
4. Relevance Scoring: Score each piece of information (0-1)

Search Process:
1. First try semantic understanding of the query
2. Then look for direct keyword matches
3. Consider contextual relationships
4. Score and rank results by relevance
5. Return only the most relevant information

Return ONLY a JSON object (no markdown formatting) with this structure:
{
    "relevant_chunks": [
        {
            "content": "the relevant information",
            "source": "where it came from",
            "relevance_score": 0.95,
            "search_method": "semantic/keyword/contextual"
        }
    ],
    "summary": "brief summary of what was found",
    "search_methods_used": ["semantic", "keyword", "contextual"]
}""",
            llm_config={
                "config_list": config_list,
                "temperature": 0.3,  # Lower temperature for more focused search
            },
            human_input_mode="NEVER",
            code_execution_config={
                "use_docker": False,
                "last_n_messages": 3,
                "work_dir": "workspace"
            }
        )

    def search(self, query: str, raw_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform semantic search on raw results.
        
        Args:
            query: The search query
            raw_results: Raw results from GraphRAG or other sources
            
        Returns:
            Dict containing:
            - relevant_chunks: List of relevant information chunks
            - relevance_scores: Scores indicating how relevant each chunk is
            - search_methods_used: List of search methods used
        """
        # Format the raw results for the agent
        formatted_results = self._format_results(raw_results)
        print("[DEBUG] Formatted results:", formatted_results)  # Debug print
        
        # Create the search prompt
        search_prompt = f"""Please analyze the following information and find what's relevant to this query: "{query}"

RAW RESULTS:
{formatted_results}

Please:
1. Break down ALL information into meaningful chunks
2. For each chunk:
   - Analyze its relevance to the query
   - Consider both direct matches and related information
   - Look for information in ALL properties and fields
   - Don't ignore any data that might be relevant
3. Return ALL relevant chunks, even if they seem partially relevant
4. Provide a relevance score (0-1) for each chunk
5. Specify which search method was used for each chunk

IMPORTANT: Look at ALL properties and their values, including nested data. Don't miss any information that might be relevant to the query.

Return ONLY a JSON object (no markdown formatting) with this structure:
{{
    "relevant_chunks": [
        {{
            "content": "the relevant information",
            "source": "where it came from",
            "relevance_score": 0.95,
            "search_method": "semantic/keyword/contextual"
        }}
    ],
    "summary": "brief summary of what was found",
    "search_methods_used": ["semantic", "keyword", "contextual"]
}}"""

        # Get the agent's response
        response = self.agent.generate_reply(
            messages=[{
                "role": "user",
                "content": search_prompt
            }],
            sender=self.agent
        )
        
        try:
            # Clean the response of any markdown formatting
            cleaned_response = response.strip()
            if cleaned_response.startswith('```'):
                # Remove markdown code block formatting
                cleaned_response = cleaned_response.split('\n', 1)[1]  # Remove first line
                if cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response.rsplit('\n', 1)[0]  # Remove last line
                # Remove language identifier if present
                if cleaned_response.startswith('json'):
                    cleaned_response = cleaned_response.split('\n', 1)[1]
            
            # Parse the cleaned response as JSON
            result = json.loads(cleaned_response)
            print("[DEBUG] Search result:", result)  # Debug print
            return result
        except json.JSONDecodeError as e:
            print(f"[DEBUG] JSON Parse Error: {str(e)}")
            print(f"[DEBUG] Raw Response: {response}")
            print(f"[DEBUG] Cleaned Response: {cleaned_response}")
            # If response isn't valid JSON, return a structured error
            return {
                "error": "Failed to parse search results",
                "raw_response": response
            }

    def _format_results(self, raw_results: Dict[str, Any]) -> str:
        """Format raw results for the search agent."""
        formatted = []
        
        # Format results from GraphRAG
        if "results" in raw_results:
            formatted.append("GRAPH RESULTS:")
            for result in raw_results["results"]:
                doc = result.get("document", {})
                if doc:
                    # Handle Node object
                    if hasattr(doc, 'properties'):
                        properties = doc.properties
                        formatted.append("\nDocument Properties:")
                        for key, value in properties.items():
                            if isinstance(value, (list, dict)):
                                formatted.append(f"{key}: {json.dumps(value, indent=2)}")
                            else:
                                formatted.append(f"{key}: {value}")
                    
                    # Handle dictionary
                    elif isinstance(doc, dict):
                        properties = doc.get("properties", {})
                        if properties:
                            formatted.append("\nDocument Properties:")
                            for key, value in properties.items():
                                if isinstance(value, (list, dict)):
                                    formatted.append(f"{key}: {json.dumps(value, indent=2)}")
                                else:
                                    formatted.append(f"{key}: {value}")
                    
                    # Add node type
                    if hasattr(doc, 'labels'):
                        formatted.append(f"\nNode Type: {list(doc.labels)}")
                    elif isinstance(doc, dict):
                        formatted.append(f"\nNode Type: {doc.get('node_type', 'Unknown')}")
                    
                    # Add connections if any
                    connections = result.get("connections", [])
                    if connections:
                        formatted.append("\nConnections:")
                        for conn in connections:
                            formatted.append(f"- {json.dumps(conn, indent=2)}")
        
        # Format any other data
        for key, value in raw_results.items():
            if key not in ["results"]:
                formatted.append(f"\n{key.upper()}:")
                if isinstance(value, (list, dict)):
                    formatted.append(json.dumps(value, indent=2))
                else:
                    formatted.append(str(value))
        
        return "\n".join(formatted)

# Create a singleton instance
search_agent = SearchAgent()

# Export function for easier access
def get_search_agent(context_builder: Optional[GraphRAGContextBuilder] = None) -> SearchAgent:
    """Get the search agent instance."""
    if context_builder:
        return SearchAgent(context_builder)
    return search_agent 