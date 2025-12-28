#!/usr/bin/env python3
"""
V2V Spatial Awareness Communication System - Demo

This script demonstrates the basic functionality of the V2V communication system
with simulated vehicles sharing spatial awareness data.
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone

from src.core.vehicle_identity import VehicleIdentity, VehicleIdentityManager
from src.core.spatial_data import SpatialData, Position, Velocity, Acceleration, VehicleState
from src.communication.security_manager import SecurityManager, SecurityConfig
from src.communication.proximity_detector import ProximityDetector, CommunicationRange
from src.communication.v2v_protocol import V2VProtocol, MessageType, V2VMessage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class V2VDemo:
    """Demo class for V2V communication system."""
    
    def __init__(self):
        self.vehicles = {}
        self.security_manager = SecurityManager(SecurityConfig())
        self.proximity_detector = ProximityDetector(CommunicationRange())
        self.protocols = {}
        self._current_positions = {}  # Track current positions for bearing calculations
        
    def create_vehicle(self, vehicle_id: str, initial_position: Position) -> VehicleIdentity:
        """Create a new vehicle for the demo."""
        vehicle = VehicleIdentity(
            vehicle_id=vehicle_id,
            manufacturer="Demo Manufacturer",
            model="Demo Model",
            year=2024,
            vin=f"DEMO{vehicle_id[-8:].upper()}"
        )
        
        # Generate keys and certificate
        vehicle.generate_key_pair()
        vehicle.create_self_signed_certificate()
        
        # Register with security manager
        self.security_manager.register_vehicle(vehicle)
        
        # Create V2V protocol
        protocol = V2VProtocol(vehicle_id, self.security_manager, self.proximity_detector)
        self.protocols[vehicle_id] = protocol
        
        # Register message handler
        protocol.register_message_handler(MessageType.SPATIAL_DATA, 
                                        self._handle_spatial_data_message)
        
        self.vehicles[vehicle_id] = vehicle
        logger.info(f"Created vehicle: {vehicle_id}")
        
        return vehicle
    
    def _handle_spatial_data_message(self, message: V2VMessage) -> None:
        """Handle received spatial data messages."""
        position = message.data.get('position', {})
        velocity = message.data.get('velocity', {})
        
        lat = position.get('latitude', 0)
        lon = position.get('longitude', 0)
        speed = velocity.get('speed', 0)
        heading = velocity.get('heading', 0)
        
        # Convert heading to compass direction
        compass_directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 
                             'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
        compass_index = int((heading + 11.25) / 22.5) % 16
        compass_direction = compass_directions[compass_index]
        
        logger.info(f"📡 Vehicle {message.sender_id} shared spatial data:")
        logger.info(f"   📍 Position: {lat:.4f}, {lon:.4f}")
        logger.info(f"   🚗 Speed: {speed:.1f} m/s ({speed * 3.6:.1f} km/h)")
        logger.info(f"   🧭 Heading: {heading:.1f}° ({compass_direction})")
        logger.info(f"   ⏰ Timestamp: {message.data.get('timestamp', 'N/A')}")
        
        # Calculate relative bearing if we have our own position
        if hasattr(self, '_current_positions') and message.sender_id in self._current_positions:
            our_position = self._current_positions[message.sender_id]
            from src.core.spatial_data import Position
            sender_position = Position(latitude=lat, longitude=lon)
            distance = our_position.distance_to(sender_position)
            bearing_to_sender = our_position.bearing_to(sender_position)
            
            bearing_compass_index = int((bearing_to_sender + 11.25) / 22.5) % 16
            bearing_compass = compass_directions[bearing_compass_index]
            
            logger.info(f"   📏 Distance: {distance:.1f} meters")
            logger.info(f"   🧭 Bearing to sender: {bearing_to_sender:.1f}° ({bearing_compass})")
    
    async def simulate_vehicle_movement(self, vehicle_id: str, duration: int = 30) -> None:
        """Simulate vehicle movement and V2V communication."""
        protocol = self.protocols[vehicle_id]
        
        # Start the protocol
        await protocol.start()
        
        logger.info(f"Starting vehicle {vehicle_id} simulation for {duration} seconds")
        
        # Simulate movement
        for i in range(duration):
            # Create spatial data (simulate GPS and sensors)
            import math
            time_offset = i / 10.0  # Slow movement
            
            # Simulate circular movement
            center_lat = 37.7749 + (hash(vehicle_id) % 100) / 100000  # Slight offset per vehicle
            center_lon = -122.4194 + (hash(vehicle_id) % 100) / 100000
            
            radius = 50.0  # 50 meter radius
            lat_offset = radius * math.cos(time_offset) / 111000
            lon_offset = radius * math.sin(time_offset) / (111000 * math.cos(math.radians(center_lat)))
            
            position = Position(
                latitude=center_lat + lat_offset,
                longitude=center_lon + lon_offset,
                altitude=0.0,
                accuracy=1.0,
                timestamp=datetime.now(timezone.utc)
            )
            
            velocity = Velocity(
                speed=10.0 + (hash(vehicle_id) % 10),  # Vary speed per vehicle
                heading=(time_offset * 36) % 360,  # Gradual heading change
                accuracy=0.1,
                timestamp=datetime.now(timezone.utc)
            )
            
            acceleration = Acceleration(
                linear_acceleration=0.0,
                accuracy=0.1,
                timestamp=datetime.now(timezone.utc)
            )
            
            spatial_data = SpatialData(
                vehicle_id=vehicle_id,
                position=position,
                velocity=velocity,
                acceleration=acceleration,
                state=VehicleState.MOVING,
                confidence=0.95
            )
            
            # Update proximity detector
            self.proximity_detector.update_vehicle_position(spatial_data)
            
            # Store current position for bearing calculations
            self._current_positions[vehicle_id] = position
            
            # Create and send spatial data message
            message = V2VMessage(
                message_id=f"spatial_{vehicle_id}_{i}",
                message_type=MessageType.SPATIAL_DATA,
                sender_id=vehicle_id,
                priority=spatial_data.get_communication_priority(),
                data={
                    'vehicle_id': vehicle_id,
                    'position': {
                        'latitude': position.latitude,
                        'longitude': position.longitude,
                        'altitude': position.altitude,
                        'accuracy': position.accuracy
                    },
                    'velocity': {
                        'speed': velocity.speed,
                        'heading': velocity.heading,
                        'accuracy': velocity.accuracy
                    },
                    'state': spatial_data.state.value,
                    'confidence': spatial_data.confidence,
                    'timestamp': spatial_data.timestamp.isoformat()
                },
                encrypted=True
            )
            
            # Send message
            await protocol.send_message(message)
            
            # Print detailed vehicle status every 5 seconds
            if i % 5 == 0:
                stats = protocol.get_protocol_statistics()
                nearby = self.proximity_detector.get_nearby_vehicles(vehicle_id)
                
                # Convert heading to compass direction
                compass_directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 
                                     'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
                compass_index = int((velocity.heading + 11.25) / 22.5) % 16
                compass_direction = compass_directions[compass_index]
                
                logger.info(f"🚗 Vehicle {vehicle_id} Status:")
                logger.info(f"   📍 Position: {position.latitude:.4f}, {position.longitude:.4f}")
                logger.info(f"   🚗 Speed: {velocity.speed:.1f} m/s ({velocity.speed * 3.6:.1f} km/h)")
                logger.info(f"   🧭 Heading: {velocity.heading:.1f}° ({compass_direction})")
                logger.info(f"   📡 Messages: Sent {stats['message_stats']['messages_sent']}, "
                           f"Received {stats['message_stats']['messages_received']}")
                logger.info(f"   👥 Nearby vehicles: {len(nearby)} {list(nearby) if nearby else ''}")
                logger.info("   " + "─" * 50)
            
            await asyncio.sleep(1.0)  # 1 second intervals
        
        # Stop the protocol
        await protocol.stop()
        logger.info(f"Vehicle {vehicle_id} simulation completed")
    
    async def run_demo(self) -> None:
        """Run the V2V communication demo."""
        logger.info("🚗 Starting V2V Spatial Awareness Communication Demo")
        logger.info("=" * 60)
        logger.info("This demo shows vehicles sharing spatial awareness data including:")
        logger.info("📍 GPS Position (latitude, longitude)")
        logger.info("🚗 Speed (m/s and km/h)")
        logger.info("🧭 Heading (degrees and compass direction)")
        logger.info("📏 Distance and bearing between vehicles")
        logger.info("📡 Real-time V2V communication")
        logger.info("=" * 60)
        
        # Create multiple vehicles with realistic starting positions
        # Simulate vehicles on different roads/intersections in San Francisco
        vehicles = [
            ("vehicle_001", Position(latitude=37.7749, longitude=-122.4194)),  # Market St & 5th St
            ("vehicle_002", Position(latitude=37.7849, longitude=-122.4094)),  # Union Square area
            ("vehicle_003", Position(latitude=37.7649, longitude=-122.4294)),  # Mission District
        ]
        
        for vehicle_id, position in vehicles:
            self.create_vehicle(vehicle_id, position)
        
        # Start proximity monitoring
        await self.proximity_detector.start_proximity_monitoring()
        
        # Run vehicle simulations concurrently
        tasks = []
        for vehicle_id, _ in vehicles:
            task = asyncio.create_task(self.simulate_vehicle_movement(vehicle_id, 20))
            tasks.append(task)
        
        # Wait for all simulations to complete
        await asyncio.gather(*tasks)
        
        # Stop proximity monitoring
        await self.proximity_detector.stop_proximity_monitoring()
        
        # Print final statistics
        logger.info("=" * 60)
        logger.info("📊 Final Demo Statistics")
        logger.info("=" * 60)
        
        for vehicle_id, _ in vehicles:
            if vehicle_id in self.protocols:
                stats = self.protocols[vehicle_id].get_protocol_statistics()
                logger.info(f"🚗 Vehicle {vehicle_id}:")
                logger.info(f"   📡 Sent {stats['message_stats']['messages_sent']} messages")
                logger.info(f"   📡 Received {stats['message_stats']['messages_received']} messages")
                
                # Show final position and heading
                if vehicle_id in self._current_positions:
                    final_pos = self._current_positions[vehicle_id]
                    logger.info(f"   📍 Final Position: {final_pos.latitude:.4f}, {final_pos.longitude:.4f}")
        
        proximity_stats = self.proximity_detector.get_communication_statistics()
        security_stats = self.security_manager.get_security_statistics()
        
        logger.info(f"👥 Total vehicles: {proximity_stats['total_vehicles']}")
        logger.info(f"🔗 Active connections: {proximity_stats['active_connections']}")
        logger.info(f"🔐 Registered vehicles: {security_stats['registered_vehicles']}")
        logger.info("=" * 60)
        logger.info("✅ Demo completed successfully!")
        logger.info("The demo demonstrated secure V2V communication with detailed")
        logger.info("spatial awareness data including position, speed, and directional information.")


async def main():
    """Main demo function."""
    demo = V2VDemo()
    
    try:
        await demo.run_demo()
    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
