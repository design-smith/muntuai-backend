import os
from dotenv import load_dotenv
import autogen
from datetime import datetime, timedelta
import json
from backend.agents.utils import get_current_datetime, format_datetime_for_prompt
from backend.GraphRAG.graphrag.engine.context_builder import GraphRAGContextBuilder
from backend.GraphRAG.graphrag.engine.rag_engine import GraphRAGEngine
import uuid

# Load environment variables
load_dotenv()

class CalendarManager:
    def __init__(self, timezone="UTC"):
        self.schedule_file = "backend/workspace/schedule.json"
        self.timezone = timezone
        self._ensure_schedule_file()
    
    def _ensure_schedule_file(self):
        """Ensure the schedule file exists with basic structure."""
        if not os.path.exists(self.schedule_file):
            os.makedirs(os.path.dirname(self.schedule_file), exist_ok=True)
            with open(self.schedule_file, 'w') as f:
                json.dump({
                    "events": [],
                    "last_updated": datetime.now().isoformat(),
                    "timezone": self.timezone
                }, f, indent=2)
    
    def get_schedule(self):
        """Get the current schedule."""
        with open(self.schedule_file, 'r') as f:
            return json.load(f)
    
    def save_schedule(self, schedule):
        """Save the updated schedule."""
        schedule["last_updated"] = datetime.now().isoformat()
        schedule["timezone"] = self.timezone
        with open(self.schedule_file, 'w') as f:
            json.dump(schedule, f, indent=2)
    
    def check_availability(self, start_time, duration_minutes):
        """Check if a time slot is available."""
        schedule = self.get_schedule()
        start = datetime.fromisoformat(start_time)
        end = start + timedelta(minutes=duration_minutes)
        
        for event in schedule["events"]:
            event_start = datetime.fromisoformat(event["start_time"])
            event_end = datetime.fromisoformat(event["end_time"])
            
            # Check for overlap
            if (start < event_end and end > event_start):
                return False
        return True
    
    def add_event(self, title, start_time, duration_minutes, description=""):
        """Add a new event to the schedule."""
        if not self.check_availability(start_time, duration_minutes):
            return False, "Time slot is not available"
        
        schedule = self.get_schedule()
        end_time = (datetime.fromisoformat(start_time) + 
                   timedelta(minutes=duration_minutes)).isoformat()
        
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
        """Remove an event from the schedule."""
        schedule = self.get_schedule()
        for i, event in enumerate(schedule["events"]):
            if (event["title"] == event_title and 
                event["start_time"] == start_time):
                schedule["events"].pop(i)
                self.save_schedule(schedule)
                return True, "Event removed successfully"
        return False, "Event not found"
    
    def get_events_for_date(self, date):
        """Get all events for a specific date."""
        schedule = self.get_schedule()
        target_date = datetime.fromisoformat(date).date()
        
        return [
            event for event in schedule["events"]
            if datetime.fromisoformat(event["start_time"]).date() == target_date
        ]

def get_calendar_agent(name="CalendarAssistant", timezone="EST", context_builder=None):
    """Returns a configured calendar agent."""
    calendar_manager = CalendarManager(timezone=timezone)
    
    # Configure the DeepSeek API
    config_list = [
        {
            "model": "deepseek-chat",
            "api_key": os.getenv("DEEPSEEK_API_KEY"),
            "base_url": "https://api.deepseek.com/v1"
        }
    ]
    
    # Get current datetime information
    datetime_info = get_current_datetime(timezone)
    datetime_context = format_datetime_for_prompt(datetime_info)
    
    # Create the calendar agent
    calendar_agent = autogen.UserProxyAgent(
        name=name,
        system_message=f"""You are {name}, a helpful calendar management assistant. 
        Your role is to help manage and organize schedules. You can:
        - Check availability for specific time slots
        - Add new events to the calendar
        - Remove events from the calendar
        - View events for specific dates
        - Provide schedule summaries
        
        Always verify availability before scheduling new events.
        Be clear and precise with time-related information.
        Confirm actions with the user before making changes.
        
        Current time context: {datetime_context}
        """,
        llm_config={
            "config_list": config_list,
            "temperature": 0.7,
        },
        human_input_mode="NEVER",
        code_execution_config={
            "use_docker": False,
            "last_n_messages": 3,
            "work_dir": "workspace"
        }
    )
    
    # Add calendar manager to the agent's context
    calendar_agent.calendar_manager = calendar_manager
    
    # Add context builder to the agent's context
    if context_builder is None:
        graph_rag_engine = GraphRAGEngine()
        context_builder = GraphRAGContextBuilder(graph_rag_engine)
    calendar_agent.context_builder = context_builder
    
    # Add graph update method
    def update_graph_with_calendar_change(operation_type, task_details, execution_result):
        """
        Update the knowledge graph after a calendar operation.
        Handles add_event and remove_event.
        Enhanced: Handles more event properties, checks for duplicates, and robust error handling.
        """
        graph_rag_engine = calendar_agent.context_builder.graph_rag_engine
        graph_db = graph_rag_engine.graph_db
        if operation_type == "add_event" and execution_result[0]:
            # Check for duplicate event (by title and start_time)
            existing_events = graph_db.get_node("Event", {"title": task_details["title"], "start_time": task_details["start_time"]})
            if existing_events:
                # If already exists, skip creation (idempotency)
                return
            event_id = str(uuid.uuid4())
            event_props = {
                "id": event_id,
                "title": task_details["title"],
                "start_time": task_details["start_time"],
                "end_time": (datetime.fromisoformat(task_details["start_time"]) + timedelta(minutes=task_details["duration_minutes"])) .isoformat(),
                "description": task_details.get("description", ""),
                "source": "calendar_agent",
                "created_at": datetime.now().isoformat(),
                "status": "scheduled"
            }
            # Optional properties
            if "recurrence" in task_details:
                event_props["recurrence"] = task_details["recurrence"]
            if "category" in task_details:
                event_props["category"] = task_details["category"]
            graph_db.create_node("Event", event_props)
            # Relationships: attendees
            if "attendees" in task_details and task_details["attendees"]:
                for person_id in task_details["attendees"]:
                    graph_db.create_relationship(
                        person_id, event_id, "PARTICIPATES_IN", {"role": "attendee"}
                    )
            # Relationship: location
            if "location" in task_details and task_details["location"]:
                location_id = task_details["location"]  # In real use, resolve or create location node
                graph_db.create_relationship(
                    event_id, location_id, "LOCATED_AT", {}
                )
        elif operation_type == "remove_event" and execution_result[0]:
            # Mark event as canceled (find by title and start_time)
            event_nodes = graph_db.get_node("Event", {"title": task_details["title"], "start_time": task_details["start_time"]})
            if event_nodes:
                event_id = event_nodes[0]["id"]
                graph_db.update_node(event_id, {
                    "status": "canceled",
                    "canceled_at": datetime.now().isoformat()
                })
            else:
                # Event not found, nothing to update
                pass
    calendar_agent.update_graph_with_calendar_change = update_graph_with_calendar_change
    
    return calendar_agent 

# Example: wrap add_event and remove_event to update graph after success
# (In a real system, this would be part of the agent's main execution logic)
def add_event_and_update_graph(agent, title, start_time, duration_minutes, description=""):
    result = agent.calendar_manager.add_event(title, start_time, duration_minutes, description)
    if result[0]:
        agent.update_graph_with_calendar_change("add_event", {
            "title": title,
            "start_time": start_time,
            "duration_minutes": duration_minutes,
            "description": description
        }, result)
    return result

def remove_event_and_update_graph(agent, event_title, start_time):
    result = agent.calendar_manager.remove_event(event_title, start_time)
    if result[0]:
        agent.update_graph_with_calendar_change("remove_event", {
            "title": event_title,
            "start_time": start_time
        }, result)
    return result 