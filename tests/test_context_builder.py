import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from backend.GraphRAG.graphrag.engine.context_builder import GraphRAGContextBuilder

class MockGraphRAGEngine:
    def retrieve_with_context(self, query_text, filters=None):
        return {
            "results": [
                {"document": {"node_type": "Task", "text": "Finish report", "score": 0.95}},
                {"document": {"node_type": "Event", "title": "Team Meeting", "score": 0.85}},
                {"document": {"node_type": "Note", "text": "Random note", "score": 0.5}},
            ],
            "graph_summary": {"total_nodes": 3, "total_relationships": 2}
        }

def test_format_for_agent():
    builder = GraphRAGContextBuilder(MockGraphRAGEngine(), config={"relevance_threshold": 0.8, "max_items": 2})
    result = builder.format_for_agent("test query", user_id="u1", agent_type="primary")
    assert "summary" in result
    assert "actionable_items" in result
    assert len(result["actionable_items"]) == 2
    assert "Task" in result["summary"]
    assert "Event" in result["summary"]
    assert "Note" not in result["summary"]

def test_filter_relevant():
    builder = GraphRAGContextBuilder(MockGraphRAGEngine(), config={"relevance_threshold": 0.9})
    results = MockGraphRAGEngine().retrieve_with_context("test")
    filtered = builder.filter_relevant(results, agent_type="primary")
    assert len(filtered["results"]) == 1
    assert filtered["results"][0]["document"]["node_type"] == "Task"

def test_extract_actionable_items():
    builder = GraphRAGContextBuilder(MockGraphRAGEngine())
    results = MockGraphRAGEngine().retrieve_with_context("test")
    items = builder.extract_actionable_items(results)
    assert any(i["node_type"] == "Task" for i in items)
    assert any(i["node_type"] == "Event" for i in items)
    assert all(i["node_type"] in ["Task", "Event"] for i in items)

def test_format_summary():
    builder = GraphRAGContextBuilder(MockGraphRAGEngine())
    results = MockGraphRAGEngine().retrieve_with_context("test")
    summary = builder.format_summary(results)
    assert "Task" in summary
    assert "Event" in summary
    assert "Note" in summary 