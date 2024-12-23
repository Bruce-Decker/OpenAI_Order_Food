from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from openai import OpenAI
from enum import Enum
import os
import json
import logging
from dotenv import load_dotenv
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enums for item types
class ItemType(str, Enum):
    BURGER = "burger"
    FRIES = "fries"
    DRINK = "drink"

class ActionType(str, Enum):
    ORDER = "order"
    CANCEL = "cancel"

# Models
class OrderItem(BaseModel):
    item_type: ItemType
    quantity: int

class OrderHistoryItem(BaseModel):
    id: int
    action_type: ActionType
    items: List[OrderItem]
    timestamp: datetime
    display_message: Optional[str] = None

class OrderRequest(BaseModel):
    message: str

# In-memory storage
order_history: List[OrderHistoryItem] = []
next_history_id: int = 1
item_totals = {
    ItemType.BURGER: 0,
    ItemType.FRIES: 0,
    ItemType.DRINK: 0
}

# OpenAI function definitions
order_functions = [
    {
        "name": "place_order",
        "description": "Place a new order with specified items",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_type": {
                                "type": "string",
                                "enum": ["burger", "fries", "drink"]
                            },
                            "quantity": {
                                "type": "integer",
                                "minimum": 1
                            }
                        },
                        "required": ["item_type", "quantity"]
                    }
                }
            },
            "required": ["items"]
        }
    },
    {
        "name": "cancel_items",
        "description": "Cancel specified items from the order totals",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_type": {
                                "type": "string",
                                "enum": ["burger", "fries", "drink"]
                            },
                            "quantity": {
                                "type": "integer",
                                "minimum": 1
                            }
                        },
                        "required": ["item_type", "quantity"]
                    }
                }
            },
            "required": ["items"]
        }
    }
]

def place_order(items: List[dict]) -> dict:
    global next_history_id
    try:
        logger.info(f"Attempting to place order with items: {json.dumps(items, indent=2)}")
        
        # Validate items before processing
        for item in items:
            if "item_type" not in item:
                raise ValueError("Missing item_type in order item")
            if "quantity" not in item:
                raise ValueError("Missing quantity in order item")
            try:
                ItemType(item["item_type"])  # Validate item type
            except ValueError:
                raise ValueError(f"Invalid item type: {item['item_type']}")
            if not isinstance(item["quantity"], int) or item["quantity"] < 1:
                raise ValueError(f"Invalid quantity: {item['quantity']}")
        
        # Create order history item
        history_item = OrderHistoryItem(
            id=next_history_id,
            action_type=ActionType.ORDER,
            items=[OrderItem(**item) for item in items],
            timestamp=datetime.now()
        )
        order_history.append(history_item)
        next_history_id += 1
        
        # Update totals
        for item in items:
            item_type = ItemType(item["item_type"])
            quantity = item["quantity"]
            item_totals[item_type] += quantity
        
        logger.info(f"Successfully placed order")
        return {
            "status": "success",
            "message": "Order placed successfully",
            "history": [item.model_dump() for item in order_history],
            "totals": item_totals
        }
    except ValueError as e:
        logger.error(f"Validation error in place_order: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error placing order: {str(e)}", exc_info=True)
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Items that caused error: {json.dumps(items, indent=2)}")
        raise HTTPException(status_code=500, detail=f"Failed to place order: {str(e)}")

def cancel_items(items: List[dict]) -> dict:
    global next_history_id
    try:
        logger.info(f"Attempting to cancel items: {json.dumps(items, indent=2)}")
        
        # Check if this is a cancel all orders request
        if len(items) > 0 and isinstance(items[0], dict) and items[0].get('cancel_all', False):
            # Get all cancelled order numbers by parsing cancellation messages
            cancelled_order_ids = set()
            for item in order_history:
                if item.action_type == ActionType.CANCEL and item.display_message:
                    # Check for individual order cancellations
                    if "Cancelled order #" in item.display_message:
                        try:
                            # Extract the order number from messages like "Cancelled order #2: ..."
                            order_num = int(item.display_message.split("#")[1].split(":")[0])
                            cancelled_order_ids.add(order_num)
                        except (IndexError, ValueError):
                            continue
                    # Check for "cancel all" operations
                    elif "Cancelled all orders" in item.display_message:
                        # All orders up to this point should be considered cancelled
                        cancelled_order_ids.update(
                            order.id for order in order_history 
                            if order.action_type == ActionType.ORDER 
                            and order.id < item.id
                        )
            
            # Get orders that haven't been cancelled
            active_orders = [
                order for order in order_history 
                if order.action_type == ActionType.ORDER 
                and order.id not in cancelled_order_ids
            ]
            
            if not active_orders:
                return {
                    "status": "error",
                    "message": "No active orders to cancel",
                    "display_message": "No active orders to cancel",
                    "history": [item.model_dump() for item in order_history],
                    "totals": item_totals
                }
            
            # Reset totals based on active orders
            for item_type in ItemType:
                item_totals[item_type] = 0
            
            # Create cancellation history item with proper grammar
            order_count = len(active_orders)
            order_text = "order" if order_count == 1 else "orders"
            history_item = OrderHistoryItem(
                id=next_history_id,
                action_type=ActionType.CANCEL,
                items=[],  # Empty items list for cancel all
                timestamp=datetime.now(),
                display_message=f"Cancelled all orders ({order_count} {order_text})"
            )
            order_history.append(history_item)
            next_history_id += 1
            
            return {
                "status": "success",
                "message": "All orders cancelled successfully",
                "display_message": history_item.display_message,
                "history": [item.model_dump() for item in order_history],
                "totals": item_totals
            }
        
        # Check if this is an order-specific cancellation
        order_number = None
        cancelled_order = None
        if len(items) > 0 and isinstance(items[0], dict) and 'order_number' in items[0]:
            order_number = items[0]['order_number']
            # Find the original order
            cancelled_order = next((order for order in order_history if order.id == order_number and order.action_type == ActionType.ORDER), None)
            if not cancelled_order:
                return {
                    "status": "error",
                    "message": f"Order #{order_number} not found or already cancelled",
                    "display_message": f"Error: Order #{order_number} does not exist",
                    "history": [item.model_dump() for item in order_history],
                    "totals": item_totals
                }
            # Use the items from the original order for cancellation
            items = [{"item_type": item.item_type.value, "quantity": item.quantity} for item in cancelled_order.items]
        elif not items:  # If no items and no order number
            return {
                "status": "error",
                "message": "No items specified for cancellation",
                "display_message": "Error: No items specified for cancellation",
                "history": [item.model_dump() for item in order_history],
                "totals": item_totals
            }
        
        # Create cancellation history item
        history_item = OrderHistoryItem(
            id=next_history_id,
            action_type=ActionType.CANCEL,
            items=[OrderItem(**item) for item in items],
            timestamp=datetime.now()
        )
        
        # Create appropriate display message
        display_message = None
        if cancelled_order:
            items_str = ", ".join(f"{item['quantity']} {item['item_type']}" for item in items)
            display_message = f"Cancelled order #{cancelled_order.id}: {items_str}"
        else:
            items_str = ", ".join(f"{item['quantity']} {item['item_type']}" for item in items)
            display_message = f"Cancelled: {items_str}"
        
        # Add display message to history item
        history_item.display_message = display_message
        order_history.append(history_item)
        next_history_id += 1
        
        # Update totals
        for item in items:
            item_type = ItemType(item["item_type"])
            quantity = item["quantity"]
            if item_totals[item_type] >= quantity:
                item_totals[item_type] -= quantity
            else:
                item_totals[item_type] = 0
        
        logger.info(f"Successfully cancelled items with display message: {display_message}")
        return {
            "status": "success",
            "message": "Items cancelled successfully",
            "display_message": display_message,
            "history": [item.model_dump() for item in order_history],
            "totals": item_totals
        }
    except Exception as e:
        logger.error(f"Error cancelling items: {str(e)}", exc_info=True)
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Items that caused error: {json.dumps(items, indent=2)}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel items: {str(e)}")

@app.post("/process-order")
async def process_order(request: OrderRequest):
    # Ensure OpenAI API key is set
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OpenAI API key not configured")
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    try:
        logger.info(f"Processing order request: {request.message}")
        
        # Call OpenAI to parse the request
        logger.info("Calling OpenAI API...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """You are a drive-thru order processing assistant. Your job is to parse customer orders and cancellations and convert them into structured data using the provided functions.

IMPORTANT RULES:
1. ALWAYS return a function call - never return a regular message
2. For ANY mention of food or drinks, create an order
3. For ANY mention of cancelling food or drinks, cancel the items
4. Default quantity is 1 if not specified
5. Food and drink items:
   - Burgers: burger, hamburger, cheeseburger
   - Fries: fries, fry, onion fries, curly fries, sweet potato fries
   - Drinks: ANY beverage, including:
     * Tea, coffee, water, juice
     * Soda: Coke, Pepsi, Sprite, etc.
     * Any other drink name or description

EXAMPLES:
Single Item Orders:
User: "I want a burger"
Response: place_order with items=[{"item_type": "burger", "quantity": 1}]

User: "I want fries"
Response: place_order with items=[{"item_type": "fries", "quantity": 1}]

User: "I want a fry"
Response: place_order with items=[{"item_type": "fries", "quantity": 1}]

User: "I want coke"
Response: place_order with items=[{"item_type": "drink", "quantity": 1}]

Multiple Item Orders:
User: "I would like one burger and an order of fries"
Response: place_order with items=[
    {"item_type": "burger", "quantity": 1},
    {"item_type": "fries", "quantity": 1}
]

User: "I want a burger and a fry"
Response: place_order with items=[
    {"item_type": "burger", "quantity": 1},
    {"item_type": "fries", "quantity": 1}
]

User: "I want a burger and fries"
Response: place_order with items=[
    {"item_type": "burger", "quantity": 1},
    {"item_type": "fries", "quantity": 1}
]

User: "I want a fry and a burger"
Response: place_order with items=[
    {"item_type": "fries", "quantity": 1},
    {"item_type": "burger", "quantity": 1}
]

User: "I want fries and a burger"
Response: place_order with items=[
    {"item_type": "fries", "quantity": 1},
    {"item_type": "burger", "quantity": 1}
]

User: "I want a burger and a drink"
Response: place_order with items=[
    {"item_type": "burger", "quantity": 1},
    {"item_type": "drink", "quantity": 1}
]

User: "I want a drink and a burger"
Response: place_order with items=[
    {"item_type": "drink", "quantity": 1},
    {"item_type": "burger", "quantity": 1}
]

User: "I want a fry and a drink"
Response: place_order with items=[
    {"item_type": "fries", "quantity": 1},
    {"item_type": "drink", "quantity": 1}
]

User: "I want fries and a drink"
Response: place_order with items=[
    {"item_type": "fries", "quantity": 1},
    {"item_type": "drink", "quantity": 1}
]

User: "I want a drink and a fry"
Response: place_order with items=[
    {"item_type": "drink", "quantity": 1},
    {"item_type": "fries", "quantity": 1}
]

User: "I want a drink and fries"
Response: place_order with items=[
    {"item_type": "drink", "quantity": 1},
    {"item_type": "fries", "quantity": 1}
]

User: "Give me fries and a drink"
Response: place_order with items=[
    {"item_type": "fries", "quantity": 1},
    {"item_type": "drink", "quantity": 1}
]

User: "Can I get a burger, fries, and a drink"
Response: place_order with items=[
    {"item_type": "burger", "quantity": 1},
    {"item_type": "fries", "quantity": 1},
    {"item_type": "drink", "quantity": 1}
]

Common Order Phrases:
- "I want X and Y"
- "Give me X and Y"
- "Can I get X and Y"
- "I'd like X and Y"
- "I'll take X and Y"
- "I would like X and Y"

Cancellation Examples:
User: "I want to cancel my burger"
Response: cancel_items with items=[{"item_type": "burger", "quantity": 1}]

User: "I want to cancel my drink"
Response: cancel_items with items=[{"item_type": "drink", "quantity": 1}]

User: "Cancel order 1"
Response: cancel_items with items=[{"order_number": 1}]

User: "Cancel order number 1"
Response: cancel_items with items=[{"order_number": 1}]

User: "I want to cancel order 1"
Response: cancel_items with items=[{"order_number": 1}]

User: "Cancel order #1"
Response: cancel_items with items=[{"order_number": 1}]

User: "Cancel order 4"
Response: cancel_items with items=[{"order_number": 4}]

User: "Cancel all orders"
Response: cancel_items with items=[{"cancel_all": true}]

User: "I want to cancel everything"
Response: cancel_items with items=[{"cancel_all": true}]

User: "Cancel all my orders"
Response: cancel_items with items=[{"cancel_all": true}]

Common Cancellation Phrases:
- "Cancel order X"
- "Cancel order number X"
- "I want to cancel order X"
- "Cancel my order X"
- "Cancel the order X"
- "Cancel order #X"
- "Cancel all orders"
- "Cancel everything"
- "Cancel all my orders"
- "I want to cancel all orders"

Remember: 
1. ALWAYS return a function call
2. ANY beverage request is a drink order
3. Quantity defaults to 1
4. Keep it simple - just map to the three item types: burger, fries, drink
5. For multiple items, include all items in the items array
6. "fry" and "fries" both map to the "fries" item type
7. Common phrases like "I want", "Give me", "Can I get" all indicate an order
8. The word "and" between items indicates multiple items in one order
9. When cancelling an order number, ONLY cancel the items from that specific order
10. Common cancellation phrases include "cancel order", "cancel order number", "I want to cancel order"
11. The word "fry" (singular) should always be treated as "fries" (plural) in the item_type
12. The order of items in the response doesn't matter, as long as all items are included
13. When someone says "a drink", it means one drink
14. When someone says "a burger", it means one burger
15. When someone says "a fry" or "fries", it means one order of fries
16. When cancelling an order, only cancel the exact items from that order, nothing more
17. The order number in the cancellation request refers to the specific order to cancel
18. Always include the order_number parameter in the response when cancelling an order
19. If the order number doesn't exist, return an empty items array and include an error message
20. The order number can be specified with or without the # symbol
21. When someone says "a burger and a fry", it means one burger and one order of fries
22. The order of items in the request doesn't matter (e.g., "a burger and a fry" is the same as "a fry and a burger")
23. Always return a place_order function call for any food or drink request
24. When cancelling an order, subtract the exact quantities from the totals
25. The totals should reflect the current state after all orders and cancellations
26. "an order of fries" means one order of fries
27. "one burger" means one burger
28. Always include a message in the cancellation response showing which order is being cancelled and its items
29. The cancellation message should follow the format "Cancelling order #X: [items]"
30. The items in the cancellation message should be listed in the same format as the order history
31. When cancelling an order, the totals must be updated by subtracting the cancelled items
32. The UI should clearly show which order is being cancelled and what items are being cancelled
33. The cancellation message should be displayed in the order history
34. The totals should be recalculated after each cancellation
35. The cancellation message should include both the order number and the items being cancelled
36. Always include a display_message parameter in the response for UI display
37. The display_message should be in the format "Cancelled order #X: [items]" or "Cancelled: [items]"
38. The display_message should be clear and concise for the UI
39. The display_message should be different from the internal message for better UI presentation
40. The display_message should be used to show the final state of the cancellation in the UI
41. When someone says to cancel all orders, use the cancel_all parameter
42. When cancelling all orders, all totals should be reset to 0
43. The display message for cancel all should show how many orders were cancelled"""},
                {"role": "user", "content": request.message}
            ],
            functions=order_functions,
            function_call="auto"
        )
        
        # Log the relevant parts of the OpenAI response
        logger.info(f"OpenAI API Response - Model: {response.model}, ID: {response.id}")
        logger.info(f"First choice message: {response.choices[0].message.content}")
        if response.choices[0].message.function_call:
            function_call = response.choices[0].message.function_call
            logger.info(f"Function call: {function_call.name}")
            try:
                args_dict = json.loads(function_call.arguments)
                logger.info(f"Arguments: {json.dumps(args_dict, indent=2)}")
            except json.JSONDecodeError:
                logger.warning(f"Could not parse function arguments: {function_call.arguments}")

        # Extract the function call
        message = response.choices[0].message
        if not message.function_call:
            logger.warning(f"No valid order found in message: {request.message}")
            raise HTTPException(status_code=400, detail="Could not understand the order. Please try rephrasing your request.")
            
        function_call = message.function_call
        try:
            args = json.loads(function_call.arguments)
            logger.info(f"Parsed arguments: {json.dumps(args, indent=2)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse function arguments: {function_call.arguments}")
            raise HTTPException(status_code=500, detail="Failed to parse order details")
        
        if function_call.name == "place_order":
            # Handle place order
            if "items" not in args:
                logger.error(f"Missing items in order arguments: {args}")
                raise HTTPException(status_code=400, detail="No items specified in the order")
            return place_order(args["items"])
        elif function_call.name == "cancel_items":
            # Handle cancel items
            if "items" not in args:
                logger.error(f"Missing items in cancel arguments: {args}")
                raise HTTPException(status_code=400, detail="No items specified for cancellation")
            return cancel_items(args["items"])
        else:
            logger.warning(f"Invalid request type: {function_call.name}")
            raise HTTPException(status_code=400, detail="Invalid request type")

    except Exception as e:
        logger.error(f"Error processing order: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/orders")
async def get_orders() -> List[OrderHistoryItem]:
    return order_history

@app.get("/totals")
async def get_totals():
    return item_totals

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
