class PlaceOrderRequest(BaseModel):
    args: AIOrder

class AIOrder(BaseModel):
    delivery_fee: Optional[float] = 0.00
    tip_amount: Optional[float] = 0.00
    pick_up_time: Optional[str] = "ASAP"
    order_notes: Optional[str] = ""
    customer_name: Optional[str] = ""
    customer_phone: Optional[str] = ""
    customer_address: Optional[str] = ""
    payment_type: Optional[str] = "Pay at the restaurant"
    credit_card_number: Optional[str] = ""
    credit_card_expiration_date: Optional[str] = ""
    credit_card_security_code: Optional[str] = ""
    credit_card_zip_code: Optional[str] = ""
    order_items: List[OrderItem]
    order_type: Optional[str] = "pick up"

class OrderItem(BaseModel):
    item_id: Optional[int] = 0
    item_name: str
    item_quantity: Optional[int] = 1
    item_base_price: Optional[float] = 0.00
    special_instructions: Optional[str] = ""
    modifiers: Optional[List[Modifier]] = None  
    item_total: Optional[float] = 0.00

class Modifier(BaseModel):
    modifier_name: str
    modifier_price: Optional[float] = 0.00
    modifier_quantity: Optional[int] = 1