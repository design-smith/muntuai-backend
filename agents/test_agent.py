from primary_agent import get_primary_agent

def chat_with_agent(agent_name="primary_agent"):
    # Get the primary agent with specified name
    agent = get_primary_agent(name=agent_name)
    
    print(f"Welcome to the {agent_name} Chat! (Type 'exit' to quit)")
    print("-" * 50)
    
    # Initialize the chat
    chat_history = []
    
    while True:
        # Get user input
        user_input = input("\nYou: ").strip()
        
        # Check if user wants to exit
        if user_input.lower() == 'exit':
            print("\nGoodbye!")
            break
        
        # Add user message to chat history
        chat_history.append({"role": "user", "content": user_input})
        
        # Get agent's response
        response = agent.generate_reply(
            messages=chat_history,
            sender=agent
        )
        
        # Add agent's response to chat history
        chat_history.append({"role": "assistant", "content": response})
        
        # Print agent's response
        print(f"\n{agent_name}:", response)

if __name__ == "__main__":
    # You can change the agent name here
    chat_with_agent("Muntu") 