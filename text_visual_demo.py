#!/usr/bin/env python3
"""
Text-Based Visual V2V Communication Demo

A text-based visualization that works in any terminal environment,
showing vehicle positions and communication in a simple grid format.
"""

import asyncio
import logging
import sys
import math
import os
from datetime import datetime, timezone

from src.core.vehicle_identity import VehicleIdentity, VehicleIdentityManager
from src.core.spatial_data import SpatialData, Position, Velocity, Acceleration, VehicleState
from src.communication.security_manager import SecurityManager, SecurityConfig
from src.communication.proximity_detector import ProximityDetector, CommunicationRange
from src.communication.v2v_protocol import V2VProtocol, MessageType, V2VMessage

# Configure minimal logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)


class TextVisualV2VDemo:
    """Text-based visual demonstration of V2V communication system."""
    
    def __init__(self):
        self.vehicles = {}
        self.security_manager = SecurityManager(SecurityConfig())
        self.proximity_detector = ProximityDetector(CommunicationRange())
        self.protocols = {}
        self._current_positions = {}
        self._communication_events = []
        self._grid_size = 20
        self._vehicle_symbols = {
            'vehicle_001': '🚗',
            'vehicle_002': '🚙', 
            'vehicle_003': '🚕'
        }
        
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
        self._communication_events.append({
            'from': message.sender_id,
            'timestamp': datetime.now(timezone.utc),
            'data': message.data
        })
    
    def _normalize_to_grid(self, lat: float, lon: float) -> tuple:
        """Convert GPS coordinates to grid coordinates."""
        # Normalize to our grid
        lat_min, lat_max = 37.76, 37.79
        lon_min, lon_max = -122.43, -122.40
        
        x = int((lon - lon_min) / (lon_max - lon_min) * (self._grid_size - 1))
        y = int((lat - lat_min) / (lat_max - lat_min) * (self._grid_size - 1))
        
        return max(0, min(self._grid_size - 1, x)), max(0, min(self._grid_size - 1, y))
    
    def _clear_screen(self):
        """Clear the terminal screen."""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def _draw_grid(self):
        """Draw the current state of vehicles on a text grid."""
        # Create empty grid
        grid = [['·' for _ in range(self._grid_size)] for _ in range(self._grid_size)]
        
        # Place vehicles on grid
        for vehicle_id, position in self._current_positions.items():
            x, y = self._normalize_to_grid(position.latitude, position.longitude)
            symbol = self._vehicle_symbols.get(vehicle_id, '🚗')
            grid[y][x] = symbol
        
        # Draw grid
        print("🗺️  V2V Communication Map (Text Visualization)")
        print("=" * 50)
        print("Legend: 🚗 Car A  🚙 Car B  🚕 Car C  · Empty")
        print("=" * 50)
        
        for row in grid:
            print(' '.join(row))
        
        print("=" * 50)
    
    def _print_vehicle_info(self):
        """Print detailed vehicle information."""
        for vehicle_id, position in self._current_positions.items():
            if vehicle_id in self.protocols:
                stats = self.protocols[vehicle_id].get_protocol_statistics()
                nearby = self.proximity_detector.get_nearby_vehicles(vehicle_id)
                symbol = self._vehicle_symbols.get(vehicle_id, '🚗')
                
                print(f"{symbol} {vehicle_id.upper()}: "
                      f"📍 {position.latitude:.3f},{position.longitude:.3f} | "
                      f"👥 {len(nearby)} nearby | "
                      f"📡 {stats['message_stats']['messages_sent']} msgs")
    
    def _print_communication_events(self):
        """Print recent communication events."""
        recent_events = [e for e in self._communication_events 
                        if (datetime.now(timezone.utc) - e['timestamp']).total_seconds() < 3]
        
        if recent_events:
            print("\n📡 Recent Communications:")
            for event in recent_events[-3:]:  # Show last 3 events
                sender = event['from']
                data = event['data']
                position = data.get('position', {})
                velocity = data.get('velocity', {})
                
                lat = position.get('latitude', 0)
                lon = position.get('longitude', 0)
                speed = velocity.get('speed', 0)
                heading = velocity.get('heading', 0)
                
                symbol = self._vehicle_symbols.get(sender, '🚗')
                print(f"  {symbol} {sender.upper()} → ALL: "
                      f"📍 {lat:.3f},{lon:.3f} | "
                      f"🧭 {heading:.0f}° | "
                      f"🚀 {speed*3.6:.0f}km/h")
    
    async def simulate_vehicle_movement(self, vehicle_id: str, duration: int = 20) -> None:
        """Simulate vehicle movement and V2V communication."""
        protocol = self.protocols[vehicle_id]
        await protocol.start()
        
        # Different starting positions and movement patterns
        if vehicle_id == 'vehicle_001':
            center_lat, center_lon = 37.7749, -122.4194
            base_speed = 12.0
        elif vehicle_id == 'vehicle_002':
            center_lat, center_lon = 37.7759, -122.4184
            base_speed = 15.0
        else:
            center_lat, center_lon = 37.7739, -122.4204
            base_speed = 10.0
        
        for i in range(duration):
            time_offset = i / 5.0
            
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
            
            # Update display every second
            if i % 1 == 0:
                self._clear_screen()
                self._draw_grid()
                self._print_vehicle_info()
                self._print_communication_events()
                print(f"\n⏰ Time: {i+1}/{duration} seconds")
                print("Press Ctrl+C to stop early")
                
                await asyncio.sleep(1.0)
            else:
                await asyncio.sleep(0.1)
        
        await protocol.stop()
    
    async def run_text_visual_demo(self) -> None:
        """Run the text-based visual V2V communication demo."""
        print("🚗 Starting Text-Based Visual V2V Communication Demo")
        print("=" * 60)
        print("This demo shows:")
        print("• Vehicle positions on a text-based map")
        print("• Real-time movement and communication")
        print("• Communication events and statistics")
        print("• Works in any terminal environment")
        print("=" * 60)
        print("Starting in 3 seconds...")
        await asyncio.sleep(3)
        
        # Create vehicles with realistic starting positions
        vehicles = [
            ("vehicle_001", Position(latitude=37.7749, longitude=-122.4194)),
            ("vehicle_002", Position(latitude=37.7759, longitude=-122.4184)),
            ("vehicle_003", Position(latitude=37.7739, longitude=-122.4204)),
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
        
        # Final display
        self._clear_screen()
        print("🎉 Text Visual Demo Completed!")
        print("=" * 50)
        print("Final Statistics:")
        
        total_messages = 0
        for vehicle_id in vehicles:
            if vehicle_id[0] in self.protocols:
                stats = self.protocols[vehicle_id[0]].get_protocol_statistics()
                messages_sent = stats['message_stats']['messages_sent']
                total_messages += messages_sent
                symbol = self._vehicle_symbols.get(vehicle_id[0], '🚗')
                print(f"{symbol} {vehicle_id[0].upper()}: {messages_sent} messages sent")
        
        print(f"📡 Total V2V messages: {total_messages}")
        print(f"👥 Total vehicles: {len(vehicles)}")
        print("✅ Demo completed successfully!")


async def main():
    """Main text visual demo function."""
    demo = TextVisualV2VDemo()
    
    try:
        await demo.run_text_visual_demo()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"Demo error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)




