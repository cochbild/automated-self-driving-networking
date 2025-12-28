#!/usr/bin/env python3
"""
Simple V2V Communication Demo

A simplified, easy-to-understand demonstration of the V2V communication system
with clear, concise output showing vehicle movement and communication.
"""

import asyncio
import logging
import sys
import math
from datetime import datetime, timezone

from src.core.vehicle_identity import VehicleIdentity, VehicleIdentityManager
from src.core.spatial_data import SpatialData, Position, Velocity, Acceleration, VehicleState
from src.communication.security_manager import SecurityManager, SecurityConfig
from src.communication.proximity_detector import ProximityDetector, CommunicationRange
from src.communication.v2v_protocol import V2VProtocol, MessageType, V2VMessage

# Configure minimal logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


class SimpleV2VDemo:
    """Simple demonstration of V2V communication system."""
    
    def __init__(self):
        self.vehicles = {}
        self.security_manager = SecurityManager(SecurityConfig())
        self.proximity_detector = ProximityDetector(CommunicationRange())
        self.protocols = {}
        self._current_positions = {}
        self._communication_events = []
        
    def create_vehicle(self, vehicle_id: str, initial_position: Position) -> VehicleIdentity:
        """Create a new vehicle for the demo."""
        vehicle = VehicleIdentity(
            vehicle_id=vehicle_id,
            manufacturer="V2V Demo",
            model="Test Vehicle",
            year=2024,
            vin=f"VIN{vehicle_id[-8:].upper()}"
        )
        
        vehicle.generate_key_pair()
        vehicle.create_self_signed_certificate()
        
        self.security_manager.register_vehicle(vehicle)
        
        protocol = V2VProtocol(vehicle_id, self.security_manager, self.proximity_detector)
        protocol.register_message_handler(MessageType.SPATIAL_DATA, self._handle_spatial_data_message)
        self.protocols[vehicle_id] = protocol
        
        self.vehicles[vehicle_id] = vehicle
        return vehicle
    
    def _handle_spatial_data_message(self, message: V2VMessage) -> None:
        """Handle received spatial data messages."""
        # Store communication event
        self._communication_events.append({
            'from': message.sender_id,
            'timestamp': datetime.now(timezone.utc),
            'data': message.data
        })
    
    def _get_compass_direction(self, heading: float) -> str:
        """Convert heading to compass direction."""
        compass_directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 
                             'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
        compass_index = int((heading + 11.25) / 22.5) % 16
        return compass_directions[compass_index]
    
    def _print_vehicle_status(self, vehicle_id: str, position: Position, velocity: Velocity, 
                            nearby_count: int, messages_sent: int):
        """Print a simple, clear vehicle status."""
        compass = self._get_compass_direction(velocity.heading)
        speed_kmh = velocity.speed * 3.6
        
        print(f"🚗 {vehicle_id.upper()}: "
              f"📍 {position.latitude:.3f},{position.longitude:.3f} | "
              f"🧭 {velocity.heading:.0f}°{compass} | "
              f"🚀 {speed_kmh:.0f}km/h | "
              f"👥 {nearby_count} nearby | "
              f"📡 {messages_sent} msgs")
    
    def _print_communication_event(self, event):
        """Print a communication event in a simple format."""
        sender = event['from']
        data = event['data']
        position = data.get('position', {})
        velocity = data.get('velocity', {})
        
        lat = position.get('latitude', 0)
        lon = position.get('longitude', 0)
        speed = velocity.get('speed', 0)
        heading = velocity.get('heading', 0)
        compass = self._get_compass_direction(heading)
        
        print(f"📡 {sender.upper()} → ALL: "
              f"📍 {lat:.3f},{lon:.3f} | "
              f"🧭 {heading:.0f}°{compass} | "
              f"🚀 {speed*3.6:.0f}km/h")
    
    async def simulate_vehicle_movement(self, vehicle_id: str, duration: int = 20) -> None:
        """Simulate vehicle movement and V2V communication."""
        protocol = self.protocols[vehicle_id]
        await protocol.start()
        
        # Different starting positions and movement patterns
        if vehicle_id == 'vehicle_001':
            # Vehicle 1: Downtown area - circular movement
            center_lat, center_lon = 37.7749, -122.4194
            base_speed = 12.0
        elif vehicle_id == 'vehicle_002':
            # Vehicle 2: Close to downtown - linear movement
            center_lat, center_lon = 37.7759, -122.4184
            base_speed = 15.0
        else:
            # Vehicle 3: Also close - figure-8 pattern
            center_lat, center_lon = 37.7739, -122.4204
            base_speed = 10.0
        
        for i in range(duration):
            time_offset = i / 5.0  # Slower movement for clarity
            
            # Different movement patterns
            if vehicle_id == 'vehicle_001':
                # Circular movement
                radius = 0.002
                lat_offset = radius * math.cos(time_offset)
                lon_offset = radius * math.sin(time_offset)
                speed = base_speed + 3 * math.sin(time_offset * 0.5)
                heading = (time_offset * 20) % 360
                
            elif vehicle_id == 'vehicle_002':
                # Linear movement with slight curve
                lat_offset = time_offset * 0.001
                lon_offset = 0.0005 * math.sin(time_offset * 2)
                speed = base_speed + 2 * math.cos(time_offset * 0.3)
                heading = 180 + 30 * math.sin(time_offset)
                
            else:
                # Figure-8 pattern
                radius = 0.0015
                lat_offset = radius * math.sin(time_offset)
                lon_offset = radius * math.sin(time_offset * 2)
                speed = base_speed + 4 * math.cos(time_offset * 0.7)
                heading = (time_offset * 15 + 45) % 360
            
            position = Position(
                latitude=center_lat + lat_offset,
                longitude=center_lon + lon_offset,
                altitude=0.0,
                accuracy=1.0,
                timestamp=datetime.now(timezone.utc)
            )
            
            velocity = Velocity(
                speed=speed,
                heading=heading,
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
            
            # Update proximity detector and store position
            self.proximity_detector.update_vehicle_position(spatial_data)
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
            
            await protocol.send_message(message)
            
            # Print status every 3 seconds
            if i % 3 == 0:
                stats = protocol.get_protocol_statistics()
                nearby = self.proximity_detector.get_nearby_vehicles(vehicle_id)
                self._print_vehicle_status(vehicle_id, position, velocity, 
                                         len(nearby), stats['message_stats']['messages_sent'])
            
            # Print recent communication events
            recent_events = [e for e in self._communication_events 
                           if (datetime.now(timezone.utc) - e['timestamp']).total_seconds() < 1]
            for event in recent_events[-2:]:  # Show last 2 events
                if event['from'] != vehicle_id:  # Don't show our own messages
                    self._print_communication_event(event)
            
            if recent_events:
                print()  # Add spacing after communication events
            
            await asyncio.sleep(1.0)  # 1 second intervals
        
        await protocol.stop()
    
    async def run_simple_demo(self) -> None:
        """Run the simple V2V communication demo."""
        print("🚗 V2V Communication Demo - Simple View")
        print("=" * 50)
        print("Shows: Position | Direction | Speed | Nearby Vehicles | Messages")
        print("=" * 50)
        
        # Create vehicles with closer starting positions for better communication
        vehicles = [
            ("vehicle_001", Position(latitude=37.7749, longitude=-122.4194)),  # Downtown
            ("vehicle_002", Position(latitude=37.7759, longitude=-122.4184)),  # Close to downtown
            ("vehicle_003", Position(latitude=37.7739, longitude=-122.4204)),  # Also close
        ]
        
        for vehicle_id, position in vehicles:
            self.create_vehicle(vehicle_id, position)
            self._current_positions[vehicle_id] = position
        
        # Start proximity monitoring
        await self.proximity_detector.start_proximity_monitoring()
        
        # Start vehicle simulations
        tasks = []
        for vehicle_id, _ in vehicles:
            task = asyncio.create_task(self.simulate_vehicle_movement(vehicle_id, 15))
            tasks.append(task)
        
        # Wait for simulations to complete
        await asyncio.gather(*tasks)
        
        # Stop proximity monitoring
        await self.proximity_detector.stop_proximity_monitoring()
        
        # Print final summary
        print("\n" + "=" * 50)
        print("📊 FINAL SUMMARY")
        print("=" * 50)
        
        total_messages = 0
        for vehicle_id in vehicles:
            if vehicle_id[0] in self.protocols:
                stats = self.protocols[vehicle_id[0]].get_protocol_statistics()
                messages_sent = stats['message_stats']['messages_sent']
                total_messages += messages_sent
                print(f"🚗 {vehicle_id[0].upper()}: {messages_sent} messages sent")
        
        print(f"📡 Total V2V messages: {total_messages}")
        print(f"👥 Total vehicles: {len(vehicles)}")
        print("✅ Demo completed successfully!")


async def main():
    """Main simple demo function."""
    demo = SimpleV2VDemo()
    
    try:
        await demo.run_simple_demo()
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"Demo error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
