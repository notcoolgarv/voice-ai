"""Flow configuration for Pizza ordering bot conversation flow."""

from pipecat_flows import FlowArgs, FlowConfig, FlowsFunctionSchema, FlowManager, NodeConfig


def create_flow_config(ai_name: str) -> FlowConfig:
    """
    Create the conversation flow configuration for Pizza ordering bot.

    Args:
        ai_name: The name of the AI assistant (e.g., "Pizza ordering AI")

    Returns:
        FlowConfig dictionary with all conversation nodes
    """

    # Handler functions for the conversation flow
    async def start_order(args: FlowArgs, flow_manager: FlowManager) -> tuple[None, str]:
        """Start the pizza ordering process."""
        return None, "choose_pizza_type"

    async def select_size(args: FlowArgs, flow_manager: FlowManager) -> tuple[None, str]:
        """Move to size selection."""
        return None, "choose_size"

    async def add_toppings(args: FlowArgs, flow_manager: FlowManager) -> tuple[None, str]:
        """Move to toppings selection."""
        return None, "choose_toppings"

    async def skip_toppings(args: FlowArgs, flow_manager: FlowManager) -> tuple[None, str]:
        """Skip toppings and go to confirmation."""
        return None, "confirm_order"

    async def confirm(args: FlowArgs, flow_manager: FlowManager) -> tuple[None, str]:
        """Confirm the order."""
        return None, "confirm_order"

    async def complete(args: FlowArgs, flow_manager: FlowManager) -> tuple[None, str]:
        """Complete the order."""
        return None, "complete_order"

    async def cancel_order(args: FlowArgs, flow_manager: FlowManager) -> tuple[None, str]:
        """Cancel the order and start over."""
        return None, "greet"

    # Create function schemas
    start_order_func = FlowsFunctionSchema(
        name="start_order",
        handler=start_order,
        description="User wants to order a pizza.",
        properties={},
        required=[],
    )

    select_size_func = FlowsFunctionSchema(
        name="select_size",
        handler=select_size,
        description="User has chosen a pizza type, move to size selection.",
        properties={},
        required=[],
    )

    add_toppings_func = FlowsFunctionSchema(
        name="add_toppings",
        handler=add_toppings,
        description="User has chosen a size, ask about extra toppings.",
        properties={},
        required=[],
    )

    skip_toppings_func = FlowsFunctionSchema(
        name="skip_toppings",
        handler=skip_toppings,
        description="User doesn't want extra toppings.",
        properties={},
        required=[],
    )

    confirm_func = FlowsFunctionSchema(
        name="confirm",
        handler=confirm,
        description="User has chosen toppings, move to confirmation.",
        properties={},
        required=[],
    )

    complete_func = FlowsFunctionSchema(
        name="complete",
        handler=complete,
        description="User confirms the order.",
        properties={},
        required=[],
    )

    cancel_order_func = FlowsFunctionSchema(
        name="cancel_order",
        handler=cancel_order,
        description="User wants to cancel or start over.",
        properties={},
        required=[],
    )

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
                "functions": [start_order_func],
            },
            "choose_pizza_type": {
                "task_messages": [
                    {
                        "role": "system",
                        "content": "Ask the user what type of pizza they'd like. Offer options: Margherita, Pepperoni, Vegetarian, Hawaiian, or Supreme. Keep it friendly and brief. Once they choose, use 'select_size'.",
                    }
                ],
                "functions": [select_size_func],
            },
            "choose_size": {
                "task_messages": [
                    {
                        "role": "system",
                        "content": "Ask the user what size they'd like: Small (10 inch), Medium (12 inch), or Large (14 inch). Mention prices: Small $10, Medium $15, Large $20. Once they choose, use 'add_toppings'.",
                    }
                ],
                "functions": [add_toppings_func],
            },
            "choose_toppings": {
                "task_messages": [
                    {
                        "role": "system",
                        "content": "Ask if they want any extra toppings. Offer: extra cheese, mushrooms, olives, bell peppers, onions, bacon, or sausage ($2 each). They can choose multiple or none. Use 'confirm' when done or 'skip_toppings' if they don't want any.",
                    }
                ],
                "functions": [skip_toppings_func, confirm_func],
            },
            "confirm_order": {
                "task_messages": [
                    {
                        "role": "system",
                        "content": "Summarize their order clearly (pizza type, size, toppings if any, and total price). Ask them to confirm. Use 'complete' if they confirm, or 'cancel_order' if they want to start over.",
                    }
                ],
                "functions": [complete_func, cancel_order_func],
            },
            "complete_order": {
                "task_messages": [
                    {
                        "role": "system",
                        "content": "Thank the user and give them a random order number. Tell them their pizza will be ready in 20-30 minutes. Be friendly and warm, then end the conversation.",
                    }
                ],
                "functions": [],
                "post_actions": [{"type": "end_conversation"}],
            },
        },
    }
