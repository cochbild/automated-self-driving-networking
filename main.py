#!/usr/bin/env python3
"""
V2V Spatial Awareness Communication System - Main Application

This is the main entry point for the Vehicle-to-Vehicle communication system
that enables autonomous vehicles to share spatial awareness data securely.
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone
from typing import Optional

from src.core.vehicle_identity import VehicleIdentity, VehicleIdentityManager
from src.core.spatial_data import SpatialData, Position, Velocity, Acceleration, VehicleState
from src.communication.security_manager import SecurityManager, SecurityConfig
from src.communication.proximity_detector import ProximityDetector, CommunicationRange
from src.communication.v2v_protocol import V2VProtocol, MessageType, V2VMessage


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('v2v_system.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class V2VSystem:
    """Main V2V communication system."""
    
    def __init__(self, vehicle_id: Optional[str] = None):
        self.vehicle_id = vehicle_id or f"vehicle_{int(datetime.now().timestamp())}"
        self.running = False
        self.shutdown_task: Optional[asyncio.Task] = None
        
        # Initialize components
        self.vehicle_identity = self._create_vehicle_identity()
        self.identity_manager = VehicleIdentityManager()
        self.security_manager = SecurityManager(SecurityConfig())
        self.proximity_detector = ProximityDetector(CommunicationRange())
        self.v2v_protocol = V2VProtocol(
            self.vehicle_id, 
            self.security_manager, 
            self.proximity_detector
        )
        
        # Register message handlers
        self._register_message_handlers()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _create_vehicle_identity(self) -> VehicleIdentity:
        """Create vehicle identity for this instance."""
        vehicle = VehicleIdentity(
            vehicle_id=self.vehicle_id,
            manufacturer="V2V Demo",
            model="Test Vehicle",
            year=2024,
            vin=f"VIN{self.vehicle_id[-8:].upper()}"
        )
        
        # Generate keys and certificate
        vehicle.generate_key_pair()
        vehicle.create_self_signed_certificate()
        
        return vehicle
    
    def _register_message_handlers(self) -> None:
        """Register message handlers for different message types."""
        
        def handle_spatial_data(message: V2VMessage) -> None:
            """Handle spatial data messages from other vehicles."""
            logger.info(f"Received spatial data from {message.sender_id}")
            # Update proximity detector with received spatial data
            if 'position' in message.data and 'velocity' in message.data:
                # Create SpatialData object from received data
                # This would be more sophisticated in a real implementation
                pass
        
        def handle_emergency_broadcast(message: V2VMessage) -> None:
            """Handle emergency broadcast messages."""
            logger.warning(f"EMERGENCY BROADCAST from {message.sender_id}: {message.data}")
            # Implement emergency response logic
        
        def handle_collision_warning(message: V2VMessage) -> None:
            """Handle collision warning messages."""
            logger.warning(f"COLLISION WARNING from {message.sender_id}: {message.data}")
            # Implement collision avoidance logic
        
        def handle_heartbeat(message: V2VMessage) -> None:
            """Handle heartbeat messages."""
            logger.debug(f"Heartbeat from {message.sender_id}")
        
        def handle_acknowledgment(message: V2VMessage) -> None:
            """Handle acknowledgment messages."""
            logger.debug(f"Acknowledgment from {message.sender_id}")
        
        # Register handlers
        self.v2v_protocol.register_message_handler(MessageType.SPATIAL_DATA, handle_spatial_data)
        self.v2v_protocol.register_message_handler(MessageType.EMERGENCY_BROADCAST, handle_emergency_broadcast)
        self.v2v_protocol.register_message_handler(MessageType.COLLISION_WARNING, handle_collision_warning)
        self.v2v_protocol.register_message_handler(MessageType.HEARTBEAT, handle_heartbeat)
        self.v2v_protocol.register_message_handler(MessageType.ACKNOWLEDGMENT, handle_acknowledgment)
    
    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        try:
            # Try to get the running event loop
            loop = asyncio.get_running_loop()
            # Store task reference to prevent garbage collection
            self.shutdown_task = loop.create_task(self.stop())
        except RuntimeError:
            # No running event loop, try to get or create one
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Store task reference to prevent garbage collection
                    self.shutdown_task = loop.create_task(self.stop())
                else:
                    # If loop is not running, schedule the coroutine
                    loop.run_until_complete(self.stop())
            except RuntimeError:
                # No event loop available, create a new one
                asyncio.run(self.stop())
    
    async def start(self) -> None:
        """Start the V2V system."""
        if self.running:
            return
        
        logger.info(f"Starting V2V system for vehicle {self.vehicle_id}")
        
        try:
            # Register vehicle identity
            self.identity_manager.register_vehicle(self.vehicle_identity)
            self.security_manager.register_vehicle(self.vehicle_identity)
            
            # Start proximity detection
            await self.proximity_detector.start_proximity_monitoring()
            
            # Start V2V protocol
            await self.v2v_protocol.start()
            
            self.running = True
            logger.info("V2V system started successfully")
            
            # Start main system loop
            await self._main_loop()
            
        except Exception as e:
            logger.error(f"Error starting V2V system: {e}")
            await self.stop()
    
    async def stop(self) -> None:
        """Stop the V2V system."""
        if not self.running:
            return
        
        logger.info("Stopping V2V system...")
        
        try:
            # Stop V2V protocol
            await self.v2v_protocol.stop()
            
            # Stop proximity detection
            await self.proximity_detector.stop_proximity_monitoring()
            
            # Revoke vehicle identity
            self.security_manager.revoke_vehicle(self.vehicle_id)
            
            self.running = False
            logger.info("V2V system stopped")
            
        except Exception as e:
            logger.error(f"Error stopping V2V system: {e}")
    
    async def _main_loop(self) -> None:
        """Main system loop."""
        while self.running:
            try:
                # Update vehicle position (simulate GPS data)
                self._update_vehicle_position()
                
                # Print system statistics periodically
                self._print_statistics()
                
                # Sleep for a short interval
                await asyncio.sleep(1.0)
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(1.0)
    
    def _update_vehicle_position(self) -> None:
        """Update vehicle position (simulate GPS data)."""
        # In a real implementation, this would read from GPS sensors
        # For simulation, we'll use a simple pattern
        
        current_time = datetime.now(timezone.utc)
        time_offset = current_time.timestamp() % 100  # Simple time-based movement
        
        # Simulate vehicle moving in a circle
        import math
        radius = 50.0  # 50 meter radius
        center_lat = 37.7749  # San Francisco coordinates
        center_lon = -122.4194
        
        lat_offset = radius * math.cos(time_offset / 10) / 111000  # Rough conversion to degrees
        lon_offset = radius * math.sin(time_offset / 10) / (111000 * math.cos(math.radians(center_lat)))
        
        position = Position(
            latitude=center_lat + lat_offset,
            longitude=center_lon + lon_offset,
            altitude=0.0,
            accuracy=1.0,
            timestamp=current_time
        )
        
        velocity = Velocity(
            speed=10.0,  # 10 m/s
            heading=(time_offset * 3.6) % 360,  # Gradual heading change
            accuracy=0.1,
            timestamp=current_time
        )
        
        acceleration = Acceleration(
            linear_acceleration=0.0,
            accuracy=0.1,
            timestamp=current_time
        )
        
        spatial_data = SpatialData(
            vehicle_id=self.vehicle_id,
            position=position,
            velocity=velocity,
            acceleration=acceleration,
            state=VehicleState.MOVING,
            confidence=0.95
        )
        
        # Update proximity detector
        self.proximity_detector.update_vehicle_position(spatial_data)
    
    def _print_statistics(self) -> None:
        """Print system statistics."""
        # Print statistics every 10 seconds
        if int(datetime.now().timestamp()) % 10 == 0:
            stats = self.v2v_protocol.get_protocol_statistics()
            proximity_stats = self.proximity_detector.get_communication_statistics()
            security_stats = self.security_manager.get_security_statistics()
            
            logger.info("=== V2V System Statistics ===")
            logger.info(f"Vehicle ID: {stats['vehicle_id']}")
            logger.info(f"Running: {stats['running']}")
            logger.info(f"Messages Sent: {stats['message_stats']['messages_sent']}")
            logger.info(f"Messages Received: {stats['message_stats']['messages_received']}")
            logger.info(f"Nearby Vehicles: {proximity_stats['total_vehicles']}")
            logger.info(f"Active Connections: {proximity_stats['active_connections']}")
            logger.info(f"Registered Vehicles: {security_stats['registered_vehicles']}")
            logger.info("=============================")


async def main():
    """Main application entry point."""
    logger.info("Starting V2V Spatial Awareness Communication System")
    
    # Create and start V2V system
    v2v_system = V2VSystem()
    
    try:
        await v2v_system.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        await v2v_system.stop()
        logger.info("V2V system shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)

