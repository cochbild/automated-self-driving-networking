"""
V2V Communication Protocol Implementation

This module implements the Vehicle-to-Vehicle communication protocol including
message handling, routing, and protocol compliance.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
import logging

from .security_manager import SecurityManager, EncryptedMessage
from .proximity_detector import ProximityDetector, ProximityEvent
from ..core.spatial_data import SpatialData, MessagePriority
from ..core.vehicle_identity import VehicleIdentity

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of V2V messages."""
    SPATIAL_DATA = "spatial_data"
    EMERGENCY_BROADCAST = "emergency_broadcast"
    TRAJECTORY_PREDICTION = "trajectory_prediction"
    COLLISION_WARNING = "collision_warning"
    LANE_CHANGE_REQUEST = "lane_change_request"
    INTERSECTION_COORDINATION = "intersection_coordination"
    HEARTBEAT = "heartbeat"
    ACKNOWLEDGMENT = "acknowledgment"


@dataclass
class V2VMessage:
    """Base V2V message structure."""
    
    message_id: str
    message_type: MessageType
    sender_id: str
    receiver_id: Optional[str] = None  # None for broadcast
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl: int = 5  # Time to live in seconds
    data: Dict[str, Any] = field(default_factory=dict)
    encrypted: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            'message_id': self.message_id,
            'message_type': self.message_type.value,
            'sender_id': self.sender_id,
            'receiver_id': self.receiver_id,
            'priority': self.priority.value,
            'timestamp': self.timestamp.isoformat(),
            'ttl': self.ttl,
            'data': self.data,
            'encrypted': self.encrypted
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'V2VMessage':
        """Create message from dictionary."""
        return cls(
            message_id=data['message_id'],
            message_type=MessageType(data['message_type']),
            sender_id=data['sender_id'],
            receiver_id=data.get('receiver_id'),
            priority=MessagePriority(data['priority']),
            timestamp=datetime.fromisoformat(data['timestamp']),
            ttl=data.get('ttl', 5),
            data=data['data'],
            encrypted=data.get('encrypted', True)
        )


@dataclass
class MessageStats:
    """Statistics for message handling."""
    
    messages_sent: int = 0
    messages_received: int = 0
    messages_dropped: int = 0
    encryption_errors: int = 0
    decryption_errors: int = 0
    authentication_failures: int = 0
    last_activity: Optional[datetime] = None


class V2VProtocol:
    """Implements the V2V communication protocol."""
    
    def __init__(self, vehicle_id: str, security_manager: SecurityManager, 
                 proximity_detector: ProximityDetector):
        self.vehicle_id = vehicle_id
        self.security_manager = security_manager
        self.proximity_detector = proximity_detector
        
        # Message handling
        self.message_handlers: Dict[MessageType, List[Callable]] = {}
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.pending_acks: Dict[str, asyncio.Event] = {}
        self.message_stats = MessageStats()
        
        # Protocol state
        self.running = False
        self.broadcast_interval = 0.1  # 100ms for spatial data
        self.heartbeat_interval = 1.0  # 1 second for heartbeat
        self._tasks: List[asyncio.Task] = []
        
        # Message routing
        self.routing_table: Dict[str, str] = {}  # vehicle_id -> next_hop
        self.message_cache: Dict[str, datetime] = {}  # message_id -> timestamp
        
    def register_message_handler(self, message_type: MessageType, 
                               handler: Callable[[V2VMessage], None]) -> None:
        """Register a handler for a specific message type."""
        if message_type not in self.message_handlers:
            self.message_handlers[message_type] = []
        self.message_handlers[message_type].append(handler)
    
    def unregister_message_handler(self, message_type: MessageType, 
                                 handler: Callable[[V2VMessage], None]) -> None:
        """Unregister a message handler."""
        if message_type in self.message_handlers:
            if handler in self.message_handlers[message_type]:
                self.message_handlers[message_type].remove(handler)
    
    async def start(self) -> None:
        """Start the V2V protocol."""
        if self.running:
            return
        
        self.running = True
        
        # Start protocol tasks
        self._tasks = [
            asyncio.create_task(self._message_processing_loop()),
            asyncio.create_task(self._broadcast_loop()),
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._cleanup_loop())
        ]
        
        # Register proximity event handler
        self.proximity_detector.add_event_callback(self._on_proximity_event)
        
        logger.info(f"V2V protocol started for vehicle {self.vehicle_id}")
    
    async def stop(self) -> None:
        """Stop the V2V protocol."""
        self.running = False
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        
        # Unregister proximity event handler
        self.proximity_detector.remove_event_callback(self._on_proximity_event)
        
        logger.info(f"V2V protocol stopped for vehicle {self.vehicle_id}")
    
    async def send_message(self, message: V2VMessage, 
                          target_vehicle: Optional[str] = None) -> bool:
        """Send a V2V message."""
        try:
            # Check if message is too old
            if self._is_message_expired(message):
                self.message_stats.messages_dropped += 1
                return False
            
            # Add to message cache to prevent duplicates
            self.message_cache[message.message_id] = datetime.now(timezone.utc)
            
            # Determine target vehicles
            if target_vehicle:
                target_vehicles = [target_vehicle]
            elif message.receiver_id:
                target_vehicles = [message.receiver_id]
            else:
                # Broadcast to nearby vehicles
                target_vehicles = self.proximity_detector.get_nearby_vehicles(self.vehicle_id)
            
            # Send to each target vehicle
            sent_count = 0
            for target in target_vehicles:
                if target != self.vehicle_id:  # Don't send to self
                    if await self._send_to_vehicle(message, target):
                        sent_count += 1
            
            if sent_count > 0:
                self.message_stats.messages_sent += sent_count
                self.message_stats.last_activity = datetime.now(timezone.utc)
                return True
            else:
                self.message_stats.messages_dropped += 1
                return False
                
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.message_stats.messages_dropped += 1
            return False
    
    async def _send_to_vehicle(self, message: V2VMessage, target_vehicle: str) -> bool:
        """Send message to a specific vehicle."""
        try:
            # Check if target is in range
            if not self.proximity_detector.is_vehicle_nearby(self.vehicle_id, target_vehicle):
                return False
            
            # Encrypt message if required
            if message.encrypted:
                encrypted_msg = self.security_manager.encrypt_message(
                    message.to_dict(),
                    self.vehicle_id,
                    target_vehicle,
                    message.message_type.value,
                    message.priority.value
                )
                # In a real implementation, this would be sent over the network
                # For now, we'll simulate by adding to the target's message queue
                await self._simulate_network_send(encrypted_msg, target_vehicle)
            else:
                # Send unencrypted (not recommended for production)
                await self._simulate_network_send(message, target_vehicle)
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending to vehicle {target_vehicle}: {e}")
            return False
    
    async def _simulate_network_send(self, message: Any, target_vehicle: str) -> None:
        """Simulate network transmission (placeholder for actual network implementation)."""
        # In a real implementation, this would use DSRC, C-V2X, or Wi-Fi Direct
        # For simulation, we'll just log the transmission
        logger.debug(f"Simulated network send to {target_vehicle}: {type(message).__name__}")
    
    async def receive_message(self, encrypted_message: EncryptedMessage) -> bool:
        """Receive and process an encrypted V2V message."""
        try:
            # Decrypt message
            message_data = self.security_manager.decrypt_message(
                encrypted_message, self.vehicle_id
            )
            
            # Create V2V message
            message = V2VMessage.from_dict(message_data)
            
            # Check for duplicates
            if message.message_id in self.message_cache:
                return False
            
            # Add to message cache
            self.message_cache[message.message_id] = datetime.now(timezone.utc)
            
            # Process message
            await self.message_queue.put(message)
            
            self.message_stats.messages_received += 1
            self.message_stats.last_activity = datetime.now(timezone.utc)
            
            return True
            
        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            self.message_stats.decryption_errors += 1
            return False
    
    async def _message_processing_loop(self) -> None:
        """Main message processing loop."""
        while self.running:
            try:
                # Get message from queue
                message = await asyncio.wait_for(
                    self.message_queue.get(), timeout=1.0
                )
                
                # Process message
                await self._process_message(message)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in message processing loop: {e}")
    
    async def _process_message(self, message: V2VMessage) -> None:
        """Process a received message."""
        try:
            # Check if message is expired
            if self._is_message_expired(message):
                return
            
            # Handle message based on type
            if message.message_type in self.message_handlers:
                for handler in self.message_handlers[message.message_type]:
                    try:
                        handler(message)
                    except Exception as e:
                        logger.error(f"Error in message handler: {e}")
            
            # Send acknowledgment if required
            if message.message_type != MessageType.ACKNOWLEDGMENT:
                await self._send_acknowledgment(message)
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def _send_acknowledgment(self, original_message: V2VMessage) -> None:
        """Send acknowledgment for a received message."""
        ack_message = V2VMessage(
            message_id=f"ack_{original_message.message_id}",
            message_type=MessageType.ACKNOWLEDGMENT,
            sender_id=self.vehicle_id,
            receiver_id=original_message.sender_id,
            priority=MessagePriority.LOW,
            data={'original_message_id': original_message.message_id},
            encrypted=True
        )
        
        await self.send_message(ack_message, original_message.sender_id)
    
    async def _broadcast_loop(self) -> None:
        """Broadcast spatial data to nearby vehicles."""
        while self.running:
            try:
                # Get current spatial data (this would come from vehicle sensors)
                spatial_data = await self._get_current_spatial_data()
                
                if spatial_data:
                    # Create spatial data message
                    message = V2VMessage(
                        message_id=f"spatial_{int(time.time() * 1000)}",
                        message_type=MessageType.SPATIAL_DATA,
                        sender_id=self.vehicle_id,
                        priority=spatial_data.get_communication_priority(),
                        data=spatial_data.to_dict() if hasattr(spatial_data, 'to_dict') else {},
                        encrypted=True
                    )
                    
                    # Broadcast to nearby vehicles
                    await self.send_message(message)
                
                await asyncio.sleep(self.broadcast_interval)
                
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}")
                await asyncio.sleep(1.0)
    
    async def _heartbeat_loop(self) -> None:
        """Send heartbeat messages to maintain connectivity."""
        while self.running:
            try:
                heartbeat_message = V2VMessage(
                    message_id=f"heartbeat_{int(time.time())}",
                    message_type=MessageType.HEARTBEAT,
                    sender_id=self.vehicle_id,
                    priority=MessagePriority.LOW,
                    data={'timestamp': datetime.now(timezone.utc).isoformat()},
                    encrypted=True
                )
                
                await self.send_message(heartbeat_message)
                await asyncio.sleep(self.heartbeat_interval)
                
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(1.0)
    
    async def _cleanup_loop(self) -> None:
        """Clean up expired messages and cache."""
        while self.running:
            try:
                current_time = datetime.now(timezone.utc)
                
                # Clean up message cache
                expired_messages = []
                for message_id, timestamp in self.message_cache.items():
                    if (current_time - timestamp).total_seconds() > 300:  # 5 minutes
                        expired_messages.append(message_id)
                
                for message_id in expired_messages:
                    del self.message_cache[message_id]
                
                # Clean up expired acknowledgments
                expired_acks = []
                for message_id, event in self.pending_acks.items():
                    if (current_time - event.created_at).total_seconds() > 30:  # 30 seconds
                        expired_acks.append(message_id)
                
                for message_id in expired_acks:
                    del self.pending_acks[message_id]
                
                await asyncio.sleep(30)  # Cleanup every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(30)
    
    def _is_message_expired(self, message: V2VMessage) -> bool:
        """Check if a message has expired."""
        age = (datetime.now(timezone.utc) - message.timestamp).total_seconds()
        return age > message.ttl
    
    async def _get_current_spatial_data(self) -> Optional[SpatialData]:
        """Get current spatial data from vehicle sensors (placeholder)."""
        # This would integrate with actual vehicle sensors
        # For now, return None to indicate no data available
        return None
    
    def _on_proximity_event(self, event: ProximityEvent) -> None:
        """Handle proximity events."""
        logger.debug(f"Proximity event: {event.event_type} for vehicle {event.vehicle_id}")
        
        # Update routing table based on proximity changes
        if event.event_type == 'vehicle_entered':
            self.routing_table[event.vehicle_id] = event.vehicle_id
        elif event.event_type == 'vehicle_exited':
            if event.vehicle_id in self.routing_table:
                del self.routing_table[event.vehicle_id]
    
    def get_protocol_statistics(self) -> Dict[str, Any]:
        """Get protocol statistics."""
        return {
            'vehicle_id': self.vehicle_id,
            'running': self.running,
            'message_stats': {
                'messages_sent': self.message_stats.messages_sent,
                'messages_received': self.message_stats.messages_received,
                'messages_dropped': self.message_stats.messages_dropped,
                'encryption_errors': self.message_stats.encryption_errors,
                'decryption_errors': self.message_stats.decryption_errors,
                'authentication_failures': self.message_stats.authentication_failures,
                'last_activity': self.message_stats.last_activity.isoformat() if self.message_stats.last_activity else None
            },
            'routing_table_size': len(self.routing_table),
            'message_cache_size': len(self.message_cache),
            'pending_acks': len(self.pending_acks)
        }

