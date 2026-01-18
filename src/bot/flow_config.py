"""Flow configuration for Pizza ordering bot conversation flow."""

from pipecat_flows import FlowArgs, FlowConfig


# Handler functions for the conversation flow
async def start_order(args: FlowArgs) -> tuple[None, str]:
    """Start the pizza ordering process."""
    return None, "choose_pizza_type"


async def select_size(args: FlowArgs) -> tuple[None, str]:
    """Move to size selection."""
    return None, "choose_size"


async def add_toppings(args: FlowArgs) -> tuple[None, str]:
    """Move to toppings selection."""
    return None, "choose_toppings"


async def skip_toppings(args: FlowArgs) -> tuple[None, str]:
    """Skip toppings and go to confirmation."""
    return None, "confirm_order"


async def confirm(args: FlowArgs) -> tuple[None, str]:
    """Confirm the order."""
    return None, "confirm_order"


async def complete(args: FlowArgs) -> tuple[None, str]:
    """Complete the order."""
    return None, "complete_order"


async def cancel_order(args: FlowArgs) -> tuple[None, str]:
    """Cancel the order and start over."""
    return None, "greet"


def create_flow_config(ai_name: str) -> FlowConfig:
    """
    Create the conversation flow configuration for Pizza ordering bot.

    Args:
        ai_name: The name of the AI assistant (e.g., "Pizza ordering AI")

    Returns:
        FlowConfig dictionary with all conversation nodes
    """
    return {
        "initial_node": "greet",
        "nodes": {
            "greet": {
                "role_messages": [
                    {
                        "role": "system",
                        "content": f"You are {ai_name}, a friendly pizza ordering assistant. Be warm, enthusiastic, and helpful. Keep responses concise and conversational.",
                    }
                ],
                "task_messages": [
                    {
                        "role": "system",
                        "content": f"Greet the user warmly and ask if they'd like to order a pizza. For example: 'Hi! Welcome to our pizzeria! I'm {ai_name}. Would you like to order a delicious pizza today?' Once they confirm they want to order, use the 'start_order' function.",
                    }
                ],
                "functions": [
                    {
                        "type": "function",
                        "function": {
                            "name": "start_order",
                            "handler": start_order,
                            "description": "User wants to order a pizza.",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    }
                ],
            },
            "choose_pizza_type": {
                "task_messages": [
                    {
                        "role": "system",
                        "content": "Ask the user what type of pizza they'd like. Offer options: Margherita, Pepperoni, Vegetarian, Hawaiian, or Supreme. Keep it friendly and brief. For example: 'Great! What type of pizza would you like? We have Margherita, Pepperoni, Vegetarian, Hawaiian, and Supreme.' Once they choose, use 'select_size'.",
                    }
                ],
                "functions": [
                    {
                        "type": "function",
                        "function": {
                            "name": "select_size",
                            "handler": select_size,
                            "description": "User has chosen a pizza type, move to size selection.",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    }
                ],
            },
            "choose_size": {
                "task_messages": [
                    {
                        "role": "system",
                        "content": "Ask the user what size they'd like: Small (10 inch), Medium (12 inch), or Large (14 inch). Mention prices if helpful: Small $10, Medium $15, Large $20. Once they choose, use 'add_toppings' to ask about extra toppings.",
                    }
                ],
                "functions": [
                    {
                        "type": "function",
                        "function": {
                            "name": "add_toppings",
                            "handler": add_toppings,
                            "description": "User has chosen a size, ask about extra toppings.",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    }
                ],
            },
            "choose_toppings": {
                "task_messages": [
                    {
                        "role": "system",
                        "content": "Ask if they want any extra toppings. Offer: extra cheese, mushrooms, olives, bell peppers, onions, bacon, or sausage ($2 each). They can choose multiple or none. Once they're done, use 'confirm' to move to order confirmation.",
                    }
                ],
                "functions": [
                    {
                        "type": "function",
                        "function": {
                            "name": "skip_toppings",
                            "handler": skip_toppings,
                            "description": "User doesn't want extra toppings.",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "confirm",
                            "handler": confirm,
                            "description": "User has chosen toppings, move to confirmation.",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    },
                ],
            },
            "confirm_order": {
                "task_messages": [
                    {
                        "role": "system",
                        "content": "Summarize their order clearly (pizza type, size, toppings if any, and total price). Ask them to confirm: 'Does this sound good?' or 'Should I place this order?' Use 'complete' if they confirm, or 'cancel_order' if they want to start over.",
                    }
                ],
                "functions": [
                    {
                        "type": "function",
                        "function": {
                            "name": "complete",
                            "handler": complete,
                            "description": "User confirms the order.",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "cancel_order",
                            "handler": cancel_order,
                            "description": "User wants to cancel or start over.",
                            "parameters": {"type": "object", "properties": {}},
                        },
                    },
                ],
            },
            "complete_order": {
                "task_messages": [
                    {
                        "role": "system",
                        "content": "Thank the user and give them a random order number (e.g., #42, #1337). Tell them their pizza will be ready in 20-30 minutes. Be friendly and warm: 'Awesome! Your order #[number] is confirmed. Your delicious pizza will be ready in about 20-30 minutes. Thanks for ordering with us!' Then end the conversation.",
                    }
                ],
                "functions": [],
                "post_actions": [{"type": "end_conversation"}],
            },
        },
    }
