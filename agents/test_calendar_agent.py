from backend.agents.calendar_agent import get_calendar_agent
import json
from datetime import datetime, timedelta
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from backend.agents.calendar_agent import add_event_and_update_graph, remove_event_and_update_graph
import types

def test_calendar_agent():
    # Create a calendar agent
    agent = get_calendar_agent()
    
    # Test adding an event
    success, message = agent.calendar_manager.add_event(
        title="Test Meeting",
        start_time="2024-03-20T10:00:00",
        duration_minutes=60,
        description="A test meeting"
    )
    print(f"Add event result: {success}, {message}")
    
    # Test getting events for a date
    events = agent.calendar_manager.get_events_for_date("2024-03-20")
    print(f"Events for date: {events}")

def interactive_test():
    # Initialize the calendar agent
    agent = get_calendar_agent(name="CalendarAssistant")
    
    print("Welcome to the Calendar Assistant! (Type 'exit' to quit)")
    print("-" * 50)
    
    while True:
        # Get user input
        user_input = input("\nYou: ").strip()
        
        # Check if user wants to exit
        if user_input.lower() == 'exit':
            print("\nGoodbye!")
            break
        
        # Get agent's response
        response = agent.generate_reply(
            messages=[{
                "role": "user",
                "content": user_input
            }],
            sender=agent
        )
        
        print(f"\nCalendar Assistant: {response}")

class MockGraphDB:
    def __init__(self):
        self.created_nodes = []
        self.updated_nodes = []
        self.created_relationships = []
        self.queried_nodes = []
    def create_node(self, label, props):
        print(f"[MockGraphDB] create_node: label={label}, props={props}")
        self.created_nodes.append((label, props))
        return props.get("id", "mock_id")
    def update_node(self, node_id, props):
        print(f"[MockGraphDB] update_node: node_id={node_id}, props={props}")
        self.updated_nodes.append((node_id, props))
    def create_relationship(self, source_id, target_id, rel_type, props):
        print(f"[MockGraphDB] create_relationship: {source_id} -[{rel_type}]-> {target_id}, props={props}")
        self.created_relationships.append((source_id, target_id, rel_type, props))
    def get_node(self, label, match_props):
        print(f"[MockGraphDB] get_node: label={label}, match_props={match_props}")
        self.queried_nodes.append((label, match_props))
        # Search created_nodes for a matching node
        matches = []
        for l, props in self.created_nodes:
            if l == label and all(props.get(k) == v for k, v in match_props.items()):
                matches.append(props)
        print(f"[MockGraphDB] get_node matches: {matches}")
        return matches

class MockGraphRAGEngine:
    def __init__(self, graph_db):
        self.graph_db = graph_db

class MockContextBuilder:
    def __init__(self, graph_rag_engine):
        self.graph_rag_engine = graph_rag_engine

def test_add_event_updates_graph():
    mock_db = MockGraphDB()
    mock_engine = MockGraphRAGEngine(mock_db)
    agent = get_test_calendar_agent(context_builder=MockContextBuilder(mock_engine))
    result = add_event_and_update_graph(agent, "Test Event", "2024-06-01T10:00:00", 60, "desc")
    print(f"[DEBUG] created_nodes after add: {mock_db.created_nodes}")
    assert result[0] is True
    # Check Event node created
    assert any(label == "Event" and props["title"] == "Test Event" for label, props in mock_db.created_nodes)

def test_remove_event_updates_graph():
    mock_db = MockGraphDB()
    mock_engine = MockGraphRAGEngine(mock_db)
    agent = get_test_calendar_agent(context_builder=MockContextBuilder(mock_engine))
    # First, add event so it can be removed
    add_event_and_update_graph(agent, "Test Event", "2024-06-01T10:00:00", 60, "desc")
    # Now, remove event
    result = remove_event_and_update_graph(agent, "Test Event", "2024-06-01T10:00:00")
    assert result[0] is True
    # Check update_node called with status canceled
    assert any(props.get("status") == "canceled" for node_id, props in mock_db.updated_nodes)

def test_add_event_with_attendees_and_location():
    mock_db = MockGraphDB()
    mock_engine = MockGraphRAGEngine(mock_db)
    agent = get_test_calendar_agent(context_builder=MockContextBuilder(mock_engine))
    attendees = ["person1", "person2"]
    location = "location1"
    # Add with attendees and location (no prior add)
    agent.update_graph_with_calendar_change("add_event", {
        "title": "Team Sync",
        "start_time": "2024-06-02T09:00:00",
        "duration_minutes": 30,
        "description": "desc",
        "attendees": attendees,
        "location": location
    }, (True, "Event added successfully"))
    # Check relationships
    assert any(rel[2] == "PARTICIPATES_IN" for rel in mock_db.created_relationships)
    assert any(rel[2] == "LOCATED_AT" for rel in mock_db.created_relationships)

def test_duplicate_event_addition():
    mock_db = MockGraphDB()
    mock_engine = MockGraphRAGEngine(mock_db)
    agent = get_test_calendar_agent(context_builder=MockContextBuilder(mock_engine))
    # Add event first time
    result1 = add_event_and_update_graph(agent, "Dup Event", "2024-06-03T10:00:00", 45, "desc")
    print(f"[DEBUG] created_nodes after first add: {mock_db.created_nodes}")
    # Try to add duplicate
    result2 = add_event_and_update_graph(agent, "Dup Event", "2024-06-03T10:00:00", 45, "desc")
    print(f"[DEBUG] created_nodes after duplicate add: {mock_db.created_nodes}")
    # Only one node should be created
    event_nodes = [n for n in mock_db.created_nodes if n[0] == "Event" and n[1]["title"] == "Dup Event"]
    assert len(event_nodes) == 1

def test_remove_nonexistent_event():
    mock_db = MockGraphDB()
    mock_engine = MockGraphRAGEngine(mock_db)
    agent = get_test_calendar_agent(context_builder=MockContextBuilder(mock_engine))
    # Try to remove event that doesn't exist
    result = remove_event_and_update_graph(agent, "No Event", "2024-06-04T11:00:00")
    # No update_node should be called
    assert not mock_db.updated_nodes

def test_idempotent_add_remove():
    mock_db = MockGraphDB()
    mock_engine = MockGraphRAGEngine(mock_db)
    agent = get_test_calendar_agent(context_builder=MockContextBuilder(mock_engine))
    # Add event
    add_event_and_update_graph(agent, "Idem Event", "2024-06-05T12:00:00", 30, "desc")
    # Add again (should not create duplicate)
    add_event_and_update_graph(agent, "Idem Event", "2024-06-05T12:00:00", 30, "desc")
    event_nodes = [n for n in mock_db.created_nodes if n[0] == "Event" and n[1]["title"] == "Idem Event"]
    assert len(event_nodes) == 1
    # Remove event
    remove_event_and_update_graph(agent, "Idem Event", "2024-06-05T12:00:00")
    # Remove again (should not update anything)
    remove_event_and_update_graph(agent, "Idem Event", "2024-06-05T12:00:00")
    # Only one update_node with status canceled
    canceled_updates = [u for u in mock_db.updated_nodes if u[1].get("status") == "canceled"]
    assert len(canceled_updates) == 1

class InMemoryCalendarManager:
    def __init__(self, timezone="UTC"):
        self.timezone = timezone
        self._schedule = {
            "events": [],
            "last_updated": datetime.now().isoformat(),
            "timezone": self.timezone
        }
    def get_schedule(self):
        return self._schedule
    def save_schedule(self, schedule):
        self._schedule = schedule
    def check_availability(self, start_time, duration_minutes):
        schedule = self.get_schedule()
        start = datetime.fromisoformat(start_time)
        end = start + timedelta(minutes=duration_minutes)
        for event in schedule["events"]:
            event_start = datetime.fromisoformat(event["start_time"])
            event_end = datetime.fromisoformat(event["end_time"])
            if (start < event_end and end > event_start):
                return False
        return True
    def add_event(self, title, start_time, duration_minutes, description=""):
        if not self.check_availability(start_time, duration_minutes):
            return False, "Time slot is not available"
        schedule = self.get_schedule()
        end_time = (datetime.fromisoformat(start_time) + timedelta(minutes=duration_minutes)).isoformat()
        new_event = {
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "duration_minutes": duration_minutes,
            "description": description
        }
        schedule["events"].append(new_event)
        self.save_schedule(schedule)
        return True, "Event added successfully"
    def remove_event(self, event_title, start_time):
        schedule = self.get_schedule()
        for i, event in enumerate(schedule["events"]):
            if (event["title"] == event_title and event["start_time"] == start_time):
                schedule["events"].pop(i)
                self.save_schedule(schedule)
                return True, "Event removed successfully"
        return False, "Event not found"
    def get_events_for_date(self, date):
        schedule = self.get_schedule()
        target_date = datetime.fromisoformat(date).date()
        return [
            event for event in schedule["events"]
            if datetime.fromisoformat(event["start_time"]).date() == target_date
        ]

def get_test_calendar_agent(*args, **kwargs):
    agent = get_calendar_agent(*args, **kwargs)
    agent.calendar_manager = InMemoryCalendarManager()
    return agent

if __name__ == "__main__":
    # Choose which test to run
    print("Choose test mode:")
    print("1. Run predefined test requests")
    print("2. Interactive mode")
    choice = input("Enter your choice (1 or 2): ").strip()
    
    if choice == "1":
        test_calendar_agent()
    elif choice == "2":
        interactive_test()
    else:
        print("Invalid choice. Running interactive mode by default.")
        interactive_test() 