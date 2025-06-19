#!/usr/bin/env python3
"""
POS Integration System for Restaurant API
Supports multiple POS systems with scalable architecture
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from enum import Enum
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class POSSystemType(Enum):
    """Supported POS system types"""
    SUPERMENU = "supermenu"
    CHEERSFOOD = "cheersfood"
    # Future POS systems can be added here:
    # SQUARE = "square"
    # TOAST = "toast"
    # RESY = "resy"

class OrderStatus(Enum):
    """Standard order status across all POS systems"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    READY = "ready"
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class POSOrderData(BaseModel):
    """Standardized order data format for POS systems"""
    order_id: str
    order_number: str
    restaurant_id: str
    customer_info: Dict[str, Any]
    order_items: List[Dict[str, Any]]
    order_type: str  # pickup, delivery, dine_in
    pickup_time: Optional[str] = None
    special_instructions: Optional[str] = None
    pricing: Dict[str, float]
    payment_info: Dict[str, Any]
    pos_system: POSSystemType

class POSResponse(BaseModel):
    """Standard response from POS operations"""
    success: bool
    pos_order_id: Optional[str] = None
    status: OrderStatus
    message: str
    error_details: Optional[str] = None
    estimated_ready_time: Optional[str] = None
    pos_system: POSSystemType

class BasePOSIntegration(ABC):
    """Abstract base class for all POS integrations"""
    
    def __init__(self, restaurant_id: str, config: Dict[str, Any]):
        self.restaurant_id = restaurant_id
        self.config = config
        self.pos_type = self._get_pos_type()
    
    @abstractmethod
    def _get_pos_type(self) -> POSSystemType:
        """Return the POS system type"""
        pass
    
    @abstractmethod
    async def send_order(self, order_data: POSOrderData) -> POSResponse:
        """Send order to POS system"""
        pass
    
    @abstractmethod
    async def get_order_status(self, pos_order_id: str) -> POSResponse:
        """Get order status from POS system"""
        pass
    
    @abstractmethod
    async def cancel_order(self, pos_order_id: str) -> POSResponse:
        """Cancel order in POS system"""
        pass
    
    @abstractmethod
    async def update_order(self, pos_order_id: str, updates: Dict[str, Any]) -> POSResponse:
        """Update order in POS system"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test connection to POS system"""
        pass
    
    def format_order_for_pos(self, order_data: POSOrderData) -> Dict[str, Any]:
        """Convert standardized order data to POS-specific format"""
        # Default implementation - can be overridden by specific POS classes
        return {
            "order_id": order_data.order_id,
            "order_number": order_data.order_number,
            "customer": order_data.customer_info,
            "items": order_data.order_items,
            "order_type": order_data.order_type,
            "pickup_time": order_data.pickup_time,
            "instructions": order_data.special_instructions,
            "pricing": order_data.pricing,
            "payment": order_data.payment_info
        }

class SuperMenuPOSIntegration(BasePOSIntegration):
    """SuperMenu POS system integration"""
    
    def _get_pos_type(self) -> POSSystemType:
        return POSSystemType.SUPERMENU
    
    async def send_order(self, order_data: POSOrderData) -> POSResponse:
        """Send order to SuperMenu POS"""
        try:
            logger.info(f"[SuperMenu] Sending order {order_data.order_number} to SuperMenu POS")
            
            # TODO: Replace with actual SuperMenu API call when credentials are available
            if not self._is_configured():
                return self._create_mock_response(order_data, "SuperMenu POS not configured yet")
            
            # Future implementation:
            # supermenu_order = self._format_supermenu_order(order_data)
            # response = await self._call_supermenu_api("POST", "/orders", supermenu_order)
            
            # Mock successful response for now
            return POSResponse(
                success=True,
                pos_order_id=f"SM_{order_data.order_id}",
                status=OrderStatus.CONFIRMED,
                message="Order sent to SuperMenu POS successfully",
                estimated_ready_time=self._calculate_ready_time(order_data),
                pos_system=POSSystemType.SUPERMENU
            )
            
        except Exception as e:
            logger.error(f"[SuperMenu] Error sending order: {str(e)}")
            return POSResponse(
                success=False,
                status=OrderStatus.PENDING,
                message="Failed to send order to SuperMenu POS",
                error_details=str(e),
                pos_system=POSSystemType.SUPERMENU
            )
    
    async def get_order_status(self, pos_order_id: str) -> POSResponse:
        """Get order status from SuperMenu"""
        try:
            logger.info(f"[SuperMenu] Getting status for order {pos_order_id}")
            
            if not self._is_configured():
                return self._create_mock_status_response(pos_order_id)
            
            # Future implementation:
            # response = await self._call_supermenu_api("GET", f"/orders/{pos_order_id}")
            
            return POSResponse(
                success=True,
                pos_order_id=pos_order_id,
                status=OrderStatus.PREPARING,
                message="Order is being prepared",
                pos_system=POSSystemType.SUPERMENU
            )
            
        except Exception as e:
            logger.error(f"[SuperMenu] Error getting order status: {str(e)}")
            return POSResponse(
                success=False,
                status=OrderStatus.PENDING,
                message="Failed to get order status from SuperMenu",
                error_details=str(e),
                pos_system=POSSystemType.SUPERMENU
            )
    
    async def cancel_order(self, pos_order_id: str) -> POSResponse:
        """Cancel order in SuperMenu"""
        try:
            logger.info(f"[SuperMenu] Cancelling order {pos_order_id}")
            
            if not self._is_configured():
                return POSResponse(
                    success=True,
                    pos_order_id=pos_order_id,
                    status=OrderStatus.CANCELLED,
                    message="Order cancelled (SuperMenu not configured)",
                    pos_system=POSSystemType.SUPERMENU
                )
            
            # Future implementation:
            # response = await self._call_supermenu_api("DELETE", f"/orders/{pos_order_id}")
            
            return POSResponse(
                success=True,
                pos_order_id=pos_order_id,
                status=OrderStatus.CANCELLED,
                message="Order cancelled successfully",
                pos_system=POSSystemType.SUPERMENU
            )
            
        except Exception as e:
            logger.error(f"[SuperMenu] Error cancelling order: {str(e)}")
            return POSResponse(
                success=False,
                status=OrderStatus.PENDING,
                message="Failed to cancel order in SuperMenu",
                error_details=str(e),
                pos_system=POSSystemType.SUPERMENU
            )
    
    async def update_order(self, pos_order_id: str, updates: Dict[str, Any]) -> POSResponse:
        """Update order in SuperMenu"""
        try:
            logger.info(f"[SuperMenu] Updating order {pos_order_id}")
            
            if not self._is_configured():
                return POSResponse(
                    success=True,
                    pos_order_id=pos_order_id,
                    status=OrderStatus.CONFIRMED,
                    message="Order updated (SuperMenu not configured)",
                    pos_system=POSSystemType.SUPERMENU
                )
            
            # Future implementation:
            # response = await self._call_supermenu_api("PUT", f"/orders/{pos_order_id}", updates)
            
            return POSResponse(
                success=True,
                pos_order_id=pos_order_id,
                status=OrderStatus.CONFIRMED,
                message="Order updated successfully",
                pos_system=POSSystemType.SUPERMENU
            )
            
        except Exception as e:
            logger.error(f"[SuperMenu] Error updating order: {str(e)}")
            return POSResponse(
                success=False,
                status=OrderStatus.PENDING,
                message="Failed to update order in SuperMenu",
                error_details=str(e),
                pos_system=POSSystemType.SUPERMENU
            )
    
    async def test_connection(self) -> bool:
        """Test connection to SuperMenu"""
        try:
            if not self._is_configured():
                logger.warning("[SuperMenu] SuperMenu POS not configured")
                return False
            
            # Future implementation:
            # response = await self._call_supermenu_api("GET", "/health")
            # return response.status_code == 200
            
            return True
            
        except Exception as e:
            logger.error(f"[SuperMenu] Connection test failed: {str(e)}")
            return False
    
    def _is_configured(self) -> bool:
        """Check if SuperMenu credentials are configured"""
        required_keys = ['api_key', 'api_url', 'restaurant_id']
        return all(key in self.config and self.config[key] for key in required_keys)
    
    def _format_supermenu_order(self, order_data: POSOrderData) -> Dict[str, Any]:
        """Format order for SuperMenu API"""
        # This will be implemented when SuperMenu API documentation is available
        base_order = self.format_order_for_pos(order_data)
        
        # SuperMenu-specific formatting
        supermenu_order = {
            "orderNumber": base_order["order_number"],
            "customerId": base_order["customer"]["phone"],
            "customerName": base_order["customer"]["name"],
            "orderType": base_order["order_type"].upper(),
            "items": [
                {
                    "itemId": item.get("item_id", item["item_name"]),
                    "itemName": item["item_name"],
                    "quantity": item["item_quantity"],
                    "price": item["item_base_price"],
                    "modifiers": item.get("modifiers", []),
                    "specialInstructions": item.get("special_instructions", "")
                }
                for item in base_order["items"]
            ],
            "pricing": {
                "subtotal": base_order["pricing"]["subtotal"],
                "tax": base_order["pricing"]["tax_amount"],
                "total": base_order["pricing"]["total_amount"],
                "deliveryFee": base_order["pricing"].get("delivery_fee", 0),
                "tip": base_order["pricing"].get("tip_amount", 0)
            },
            "payment": {
                "type": base_order["payment"]["payment_type"],
                "status": base_order["payment"]["payment_status"]
            },
            "specialInstructions": base_order["instructions"],
            "requestedTime": base_order["pickup_time"]
        }
        
        return supermenu_order
    
    def _create_mock_response(self, order_data: POSOrderData, message: str) -> POSResponse:
        """Create a mock response when POS is not configured"""
        return POSResponse(
            success=True,
            pos_order_id=f"MOCK_SM_{order_data.order_id}",
            status=OrderStatus.CONFIRMED,
            message=f"{message} - Mock confirmation generated",
            estimated_ready_time=self._calculate_ready_time(order_data),
            pos_system=POSSystemType.SUPERMENU
        )
    
    def _create_mock_status_response(self, pos_order_id: str) -> POSResponse:
        """Create a mock status response"""
        return POSResponse(
            success=True,
            pos_order_id=pos_order_id,
            status=OrderStatus.PREPARING,
            message="Order is being prepared (mock status)",
            pos_system=POSSystemType.SUPERMENU
        )
    
    def _calculate_ready_time(self, order_data: POSOrderData) -> str:
        """Calculate estimated ready time"""
        from datetime import datetime, timedelta
        import pytz
        
        eastern = pytz.timezone('America/New_York')
        
        if order_data.pickup_time and order_data.pickup_time.lower() not in ["asap", ""]:
            return order_data.pickup_time
        
        # Default to 25 minutes from now
        ready_time = datetime.now(eastern) + timedelta(minutes=25)
        return ready_time.strftime("%I:%M %p")

class CheersFoodPOSIntegration(BasePOSIntegration):
    """CheersFood POS system integration"""
    
    def _get_pos_type(self) -> POSSystemType:
        return POSSystemType.CHEERSFOOD
    
    async def send_order(self, order_data: POSOrderData) -> POSResponse:
        """Send order to CheersFood POS"""
        try:
            logger.info(f"[CheersFood] Sending order {order_data.order_number} to CheersFood POS")
            
            if not self._is_configured():
                return self._create_mock_response(order_data, "CheersFood POS not configured yet")
            
            # Future implementation:
            # cheersfood_order = self._format_cheersfood_order(order_data)
            # response = await self._call_cheersfood_api("POST", "/orders", cheersfood_order)
            
            return POSResponse(
                success=True,
                pos_order_id=f"CF_{order_data.order_id}",
                status=OrderStatus.CONFIRMED,
                message="Order sent to CheersFood POS successfully",
                estimated_ready_time=self._calculate_ready_time(order_data),
                pos_system=POSSystemType.CHEERSFOOD
            )
            
        except Exception as e:
            logger.error(f"[CheersFood] Error sending order: {str(e)}")
            return POSResponse(
                success=False,
                status=OrderStatus.PENDING,
                message="Failed to send order to CheersFood POS",
                error_details=str(e),
                pos_system=POSSystemType.CHEERSFOOD
            )
    
    async def get_order_status(self, pos_order_id: str) -> POSResponse:
        """Get order status from CheersFood"""
        try:
            logger.info(f"[CheersFood] Getting status for order {pos_order_id}")
            
            if not self._is_configured():
                return self._create_mock_status_response(pos_order_id)
            
            # Future implementation:
            # response = await self._call_cheersfood_api("GET", f"/orders/{pos_order_id}")
            
            return POSResponse(
                success=True,
                pos_order_id=pos_order_id,
                status=OrderStatus.PREPARING,
                message="Order is being prepared",
                pos_system=POSSystemType.CHEERSFOOD
            )
            
        except Exception as e:
            logger.error(f"[CheersFood] Error getting order status: {str(e)}")
            return POSResponse(
                success=False,
                status=OrderStatus.PENDING,
                message="Failed to get order status from CheersFood",
                error_details=str(e),
                pos_system=POSSystemType.CHEERSFOOD
            )
    
    async def cancel_order(self, pos_order_id: str) -> POSResponse:
        """Cancel order in CheersFood"""
        try:
            logger.info(f"[CheersFood] Cancelling order {pos_order_id}")
            
            if not self._is_configured():
                return POSResponse(
                    success=True,
                    pos_order_id=pos_order_id,
                    status=OrderStatus.CANCELLED,
                    message="Order cancelled (CheersFood not configured)",
                    pos_system=POSSystemType.CHEERSFOOD
                )
            
            # Future implementation:
            # response = await self._call_cheersfood_api("DELETE", f"/orders/{pos_order_id}")
            
            return POSResponse(
                success=True,
                pos_order_id=pos_order_id,
                status=OrderStatus.CANCELLED,
                message="Order cancelled successfully",
                pos_system=POSSystemType.CHEERSFOOD
            )
            
        except Exception as e:
            logger.error(f"[CheersFood] Error cancelling order: {str(e)}")
            return POSResponse(
                success=False,
                status=OrderStatus.PENDING,
                message="Failed to cancel order in CheersFood",
                error_details=str(e),
                pos_system=POSSystemType.CHEERSFOOD
            )
    
    async def update_order(self, pos_order_id: str, updates: Dict[str, Any]) -> POSResponse:
        """Update order in CheersFood"""
        try:
            logger.info(f"[CheersFood] Updating order {pos_order_id}")
            
            if not self._is_configured():
                return POSResponse(
                    success=True,
                    pos_order_id=pos_order_id,
                    status=OrderStatus.CONFIRMED,
                    message="Order updated (CheersFood not configured)",
                    pos_system=POSSystemType.CHEERSFOOD
                )
            
            # Future implementation:
            # response = await self._call_cheersfood_api("PUT", f"/orders/{pos_order_id}", updates)
            
            return POSResponse(
                success=True,
                pos_order_id=pos_order_id,
                status=OrderStatus.CONFIRMED,
                message="Order updated successfully",
                pos_system=POSSystemType.CHEERSFOOD
            )
            
        except Exception as e:
            logger.error(f"[CheersFood] Error updating order: {str(e)}")
            return POSResponse(
                success=False,
                status=OrderStatus.PENDING,
                message="Failed to update order in CheersFood",
                error_details=str(e),
                pos_system=POSSystemType.CHEERSFOOD
            )
    
    async def test_connection(self) -> bool:
        """Test connection to CheersFood"""
        try:
            if not self._is_configured():
                logger.warning("[CheersFood] CheersFood POS not configured")
                return False
            
            # Future implementation:
            # response = await self._call_cheersfood_api("GET", "/health")
            # return response.status_code == 200
            
            return True
            
        except Exception as e:
            logger.error(f"[CheersFood] Connection test failed: {str(e)}")
            return False
    
    def _is_configured(self) -> bool:
        """Check if CheersFood credentials are configured"""
        required_keys = ['api_key', 'api_url', 'restaurant_id']
        return all(key in self.config and self.config[key] for key in required_keys)
    
    def _format_cheersfood_order(self, order_data: POSOrderData) -> Dict[str, Any]:
        """Format order for CheersFood API"""
        # This will be implemented when CheersFood API documentation is available
        base_order = self.format_order_for_pos(order_data)
        
        # CheersFood-specific formatting
        cheersfood_order = {
            "order_id": base_order["order_number"],
            "customer": {
                "phone": base_order["customer"]["phone"],
                "name": base_order["customer"]["name"],
                "address": base_order["customer"].get("address", "")
            },
            "order_type": base_order["order_type"],
            "items": [
                {
                    "name": item["item_name"],
                    "qty": item["item_quantity"],
                    "price": item["item_base_price"],
                    "mods": item.get("modifiers", []),
                    "notes": item.get("special_instructions", "")
                }
                for item in base_order["items"]
            ],
            "totals": {
                "subtotal": base_order["pricing"]["subtotal"],
                "tax": base_order["pricing"]["tax_amount"],
                "total": base_order["pricing"]["total_amount"]
            },
            "payment_info": base_order["payment"],
            "notes": base_order["instructions"],
            "pickup_time": base_order["pickup_time"]
        }
        
        return cheersfood_order
    
    def _create_mock_response(self, order_data: POSOrderData, message: str) -> POSResponse:
        """Create a mock response when POS is not configured"""
        return POSResponse(
            success=True,
            pos_order_id=f"MOCK_CF_{order_data.order_id}",
            status=OrderStatus.CONFIRMED,
            message=f"{message} - Mock confirmation generated",
            estimated_ready_time=self._calculate_ready_time(order_data),
            pos_system=POSSystemType.CHEERSFOOD
        )
    
    def _create_mock_status_response(self, pos_order_id: str) -> POSResponse:
        """Create a mock status response"""
        return POSResponse(
            success=True,
            pos_order_id=pos_order_id,
            status=OrderStatus.PREPARING,
            message="Order is being prepared (mock status)",
            pos_system=POSSystemType.CHEERSFOOD
        )
    
    def _calculate_ready_time(self, order_data: POSOrderData) -> str:
        """Calculate estimated ready time"""
        from datetime import datetime, timedelta
        import pytz
        
        eastern = pytz.timezone('America/New_York')
        
        if order_data.pickup_time and order_data.pickup_time.lower() not in ["asap", ""]:
            return order_data.pickup_time
        
        # Default to 25 minutes from now
        ready_time = datetime.now(eastern) + timedelta(minutes=25)
        return ready_time.strftime("%I:%M %p")

class POSManager:
    """Central manager for all POS integrations"""
    
    def __init__(self):
        self.pos_integrations: Dict[str, Dict[POSSystemType, BasePOSIntegration]] = {}
        self.restaurant_pos_mapping: Dict[str, List[POSSystemType]] = {}
    
    def register_pos_integration(self, restaurant_id: str, pos_type: POSSystemType, config: Dict[str, Any]):
        """Register a POS integration for a restaurant"""
        if restaurant_id not in self.pos_integrations:
            self.pos_integrations[restaurant_id] = {}
            self.restaurant_pos_mapping[restaurant_id] = []
        
        # Create the appropriate POS integration instance
        if pos_type == POSSystemType.SUPERMENU:
            integration = SuperMenuPOSIntegration(restaurant_id, config)
        elif pos_type == POSSystemType.CHEERSFOOD:
            integration = CheersFoodPOSIntegration(restaurant_id, config)
        else:
            raise ValueError(f"Unsupported POS system type: {pos_type}")
        
        self.pos_integrations[restaurant_id][pos_type] = integration
        if pos_type not in self.restaurant_pos_mapping[restaurant_id]:
            self.restaurant_pos_mapping[restaurant_id].append(pos_type)
        
        logger.info(f"Registered {pos_type.value} POS integration for restaurant {restaurant_id}")
    
    def get_pos_integration(self, restaurant_id: str, pos_type: POSSystemType) -> Optional[BasePOSIntegration]:
        """Get a specific POS integration for a restaurant"""
        return self.pos_integrations.get(restaurant_id, {}).get(pos_type)
    
    def get_all_pos_integrations(self, restaurant_id: str) -> List[BasePOSIntegration]:
        """Get all POS integrations for a restaurant"""
        return list(self.pos_integrations.get(restaurant_id, {}).values())
    
    def get_primary_pos(self, restaurant_id: str) -> Optional[BasePOSIntegration]:
        """Get the primary (first registered) POS integration for a restaurant"""
        integrations = self.get_all_pos_integrations(restaurant_id)
        return integrations[0] if integrations else None
    
    async def send_order_to_all_pos(self, restaurant_id: str, order_data: POSOrderData) -> List[POSResponse]:
        """Send order to all configured POS systems for a restaurant"""
        integrations = self.get_all_pos_integrations(restaurant_id)
        if not integrations:
            logger.warning(f"No POS integrations found for restaurant {restaurant_id}")
            return []
        
        # Send to all POS systems concurrently
        tasks = [integration.send_order(order_data) for integration in integrations]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        valid_responses = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                logger.error(f"Error sending to POS {integrations[i].pos_type}: {str(response)}")
                valid_responses.append(POSResponse(
                    success=False,
                    status=OrderStatus.PENDING,
                    message=f"Failed to send to {integrations[i].pos_type.value}",
                    error_details=str(response),
                    pos_system=integrations[i].pos_type
                ))
            else:
                valid_responses.append(response)
        
        return valid_responses
    
    async def test_all_connections(self, restaurant_id: str) -> Dict[POSSystemType, bool]:
        """Test connections to all POS systems for a restaurant"""
        integrations = self.get_all_pos_integrations(restaurant_id)
        results = {}
        
        for integration in integrations:
            try:
                results[integration.pos_type] = await integration.test_connection()
            except Exception as e:
                logger.error(f"Connection test failed for {integration.pos_type}: {str(e)}")
                results[integration.pos_type] = False
        
        return results

# Global POS manager instance
pos_manager = POSManager()

def initialize_pos_systems():
    """Initialize POS systems with default configurations"""
    import os
    
    # Restaurant 1 - SuperMenu
    supermenu_config_1 = {
        'api_key': os.getenv('SUPERMENU_API_KEY_RESTAURANT_1', ''),
        'api_url': os.getenv('SUPERMENU_API_URL_RESTAURANT_1', ''),
        'restaurant_id': os.getenv('SUPERMENU_RESTAURANT_ID_1', ''),
        'webhook_url': os.getenv('SUPERMENU_WEBHOOK_URL_1', '')
    }
    
    # Restaurant 2 - CheersFood  
    cheersfood_config_2 = {
        'api_key': os.getenv('CHEERSFOOD_API_KEY_RESTAURANT_2', ''),
        'api_url': os.getenv('CHEERSFOOD_API_URL_RESTAURANT_2', ''),
        'restaurant_id': os.getenv('CHEERSFOOD_RESTAURANT_ID_2', ''),
        'webhook_url': os.getenv('CHEERSFOOD_WEBHOOK_URL_2', '')
    }
    
    try:
        # Register POS integrations
        pos_manager.register_pos_integration("1", POSSystemType.SUPERMENU, supermenu_config_1)
        pos_manager.register_pos_integration("2", POSSystemType.CHEERSFOOD, cheersfood_config_2)
        
        logger.info("POS systems initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing POS systems: {str(e)}")

def create_pos_order_data(order_data_dict: Dict[str, Any], restaurant_id: str, pos_type: POSSystemType) -> POSOrderData:
    """Convert order data dictionary to POSOrderData object"""
    return POSOrderData(
        order_id=order_data_dict.get("order_id", ""),
        order_number=order_data_dict.get("order_number", ""),
        restaurant_id=restaurant_id,
        customer_info=order_data_dict.get("customer_info", {}),
        order_items=order_data_dict.get("order_details", {}).get("items", []),
        order_type=order_data_dict.get("order_details", {}).get("order_type", "pickup"),
        pickup_time=order_data_dict.get("order_details", {}).get("pick_up_time"),
        special_instructions=order_data_dict.get("order_details", {}).get("order_notes"),
        pricing=order_data_dict.get("pricing", {}),
        payment_info=order_data_dict.get("payment", {}),
        pos_system=pos_type
    ) 