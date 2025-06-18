from primary_agent import get_primary_agent, process_request

def test_primary_agent():
    # Initialize the primary agent
    agent = get_primary_agent()
    
    print("Welcome to the Primary Assistant! (Type 'exit' to quit)")
    print("-" * 50)
    
    # Example requests to test different scenarios
    test_requests = [
        "Schedule a team meeting tomorrow at 2pm for 1 hour",
        "What's the weather like today?",
        "Add a lunch break on Friday from 12pm to 1pm",
        "Tell me a joke",
        "Check if I'm free on Monday at 3pm for a 30-minute call",
        "What's the capital of France?",
        "Show me my schedule for the next 3 days"
    ]
    
    # Process each test request
    for request in test_requests:
        print(f"\nUser: {request}")
        response = process_request(agent, request)
        print(f"\nAssistant: {response}")
        print("-" * 50)

def interactive_test():
    # Initialize the primary agent
    agent = get_primary_agent()
    
    print("Welcome to the Primary Assistant! (Type 'exit' to quit)")
    print("-" * 50)
    
    while True:
        # Get user input
        user_input = input("\nYou: ").strip()
        
        # Check if user wants to exit
        if user_input.lower() == 'exit':
            print("\nGoodbye!")
            break
        
        # Process the request
        response = process_request(agent, user_input)
        print(f"\nAssistant: {response}")

if __name__ == "__main__":
    # Choose which test to run
    print("Choose test mode:")
    print("1. Run predefined test requests")
    print("2. Interactive mode")
    choice = input("Enter your choice (1 or 2): ").strip()
    
    if choice == "1":
        test_primary_agent()
    elif choice == "2":
        interactive_test()
    else:
        print("Invalid choice. Running interactive mode by default.")
        interactive_test() 