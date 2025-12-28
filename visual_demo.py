#!/usr/bin/env python3
"""
Visual V2V Communication Demo

This script creates a real-time visual representation of the V2V communication system
showing vehicle positions, movements, and communication links.
"""

import asyncio
import logging
import sys
import math
from datetime import datetime, timezone
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for WSL
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Circle, FancyBboxPatch
import numpy as np

from src.core.vehicle_identity import VehicleIdentity, VehicleIdentityManager
from src.core.spatial_data import SpatialData, Position, Velocity, Acceleration, VehicleState
from src.communication.security_manager import SecurityManager, SecurityConfig
from src.communication.proximity_detector import ProximityDetector, CommunicationRange
from src.communication.v2v_protocol import V2VProtocol, MessageType, V2VMessage

# Configure logging
logging.basicConfig(level=logging.WARNING)  # Reduce log noise for visual demo
logger = logging.getLogger(__name__)


class VisualV2VDemo:
    """Visual demonstration of V2V communication system."""
    
    def __init__(self):
        self.vehicles = {}
        self.security_manager = SecurityManager(SecurityConfig())
        self.proximity_detector = ProximityDetector(CommunicationRange())
        self.protocols = {}
        self._current_positions = {}
        self._communication_links = []  # Store communication events
        self._vehicle_colors = {
            'vehicle_001': 'red',
            'vehicle_002': 'blue', 
            'vehicle_003': 'green'
        }
        self._vehicle_names = {
            'vehicle_001': 'Car A',
            'vehicle_002': 'Car B',
            'vehicle_003': 'Car C'
        }
        
        # Setup matplotlib
        self.fig, self.ax = plt.subplots(figsize=(12, 10))
        self.ax.set_xlim(-0.1, 1.1)
        self.ax.set_ylim(-0.1, 1.1)
        self.ax.set_aspect('equal')
        self.ax.set_title('V2V Spatial Awareness Communication System\nReal-time Vehicle Movement and Communication', 
                         fontsize=14, fontweight='bold')
        
        # Initialize plot elements
        self.vehicle_markers = {}
        self.vehicle_labels = {}
        self.communication_lines = []
        self.info_text = self.ax.text(0.02, 0.98, '', transform=self.ax.transAxes, 
                                     verticalalignment='top', fontsize=10,
                                     bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Add legend
        legend_elements = []
        for vehicle_id, color in self._vehicle_colors.items():
            legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', 
                                            markerfacecolor=color, markersize=10, 
                                            label=self._vehicle_names[vehicle_id]))
        self.ax.legend(handles=legend_elements, loc='upper right')
        
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
        # Store communication event for visualization
        self._communication_links.append({
            'from': message.sender_id,
            'to': 'broadcast',
            'timestamp': datetime.now(timezone.utc),
            'data': message.data
        })
    
    def _normalize_position(self, lat: float, lon: float) -> tuple:
        """Convert GPS coordinates to normalized plot coordinates."""
        # Simple normalization for San Francisco area
        lat_min, lat_max = 37.76, 37.79
        lon_min, lon_max = -122.43, -122.40
        
        x = (lon - lon_min) / (lon_max - lon_min)
        y = (lat - lat_min) / (lat_max - lat_min)
        
        return x, y
    
    def _update_plot(self, frame):
        """Update the plot for animation."""
        # Clear previous communication lines
        for line in self.communication_lines:
            line.remove()
        self.communication_lines.clear()
        
        # Update vehicle positions
        for vehicle_id, position in self._current_positions.items():
            x, y = self._normalize_position(position.latitude, position.longitude)
            
            if vehicle_id in self.vehicle_markers:
                self.vehicle_markers[vehicle_id].set_data([x], [y])
            else:
                # Create new marker
                color = self._vehicle_colors.get(vehicle_id, 'black')
                marker, = self.ax.plot(x, y, 'o', color=color, markersize=15, 
                                     markeredgecolor='black', markeredgewidth=2)
                self.vehicle_markers[vehicle_id] = marker
                
                # Add vehicle label
                label = self.ax.text(x, y + 0.02, self._vehicle_names[vehicle_id], 
                                   ha='center', va='bottom', fontweight='bold', fontsize=10)
                self.vehicle_labels[vehicle_id] = label
        
        # Draw communication links
        recent_communications = [link for link in self._communication_links 
                               if (datetime.now(timezone.utc) - link['timestamp']).total_seconds() < 2]
        
        for comm in recent_communications:
            if comm['from'] in self._current_positions:
                from_pos = self._current_positions[comm['from']]
                from_x, from_y = self._normalize_position(from_pos.latitude, from_pos.longitude)
                
                # Draw communication radius
                comm_circle = Circle((from_x, from_y), 0.1, fill=False, 
                                   linestyle='--', alpha=0.3, color='gray')
                self.ax.add_patch(comm_circle)
                self.communication_lines.append(comm_circle)
        
        # Update info text
        info_text = "V2V Communication Status:\n"
        for vehicle_id in self._current_positions:
            if vehicle_id in self.protocols:
                stats = self.protocols[vehicle_id].get_protocol_statistics()
                nearby = self.proximity_detector.get_nearby_vehicles(vehicle_id)
                info_text += f"{self._vehicle_names[vehicle_id]}: {len(nearby)} nearby, "
                info_text += f"{stats['message_stats']['messages_sent']} sent\n"
        
        self.info_text.set_text(info_text)
        
        return list(self.vehicle_markers.values()) + list(self.vehicle_labels.values()) + self.communication_lines + [self.info_text]
    
    async def simulate_vehicle_movement(self, vehicle_id: str, duration: int = 30) -> None:
        """Simulate vehicle movement and V2V communication."""
        protocol = self.protocols[vehicle_id]
        await protocol.start()
        
        # Get initial position from vehicle creation
        initial_pos = None
        for vid, pos in self._current_positions.items():
            if vid == vehicle_id:
                initial_pos = pos
                break
        
        if not initial_pos:
            # Create initial position based on vehicle_id
            if vehicle_id == 'vehicle_001':
                initial_pos = Position(latitude=37.7749, longitude=-122.4194)
            elif vehicle_id == 'vehicle_002':
                initial_pos = Position(latitude=37.7849, longitude=-122.4094)
            else:
                initial_pos = Position(latitude=37.7649, longitude=-122.4294)
        
        for i in range(duration):
            # Simulate realistic vehicle movement
            time_offset = i / 10.0
            
            # Different movement patterns for each vehicle
            if vehicle_id == 'vehicle_001':
                # Vehicle 1: Circular movement around downtown
                center_lat = 37.7749
                center_lon = -122.4194
                radius = 0.002  # ~200m radius
                lat_offset = radius * math.cos(time_offset)
                lon_offset = radius * math.sin(time_offset)
                speed = 12.0 + 3 * math.sin(time_offset * 0.5)
                heading = (time_offset * 20) % 360
                
            elif vehicle_id == 'vehicle_002':
                # Vehicle 2: Linear movement north-south
                center_lat = 37.7849 + time_offset * 0.001
                center_lon = -122.4094
                lat_offset = 0
                lon_offset = 0.0005 * math.sin(time_offset * 2)
                speed = 15.0 + 2 * math.cos(time_offset * 0.3)
                heading = 180 + 30 * math.sin(time_offset)
                
            else:
                # Vehicle 3: Figure-8 pattern
                center_lat = 37.7649
                center_lon = -122.4294
                radius = 0.0015
                lat_offset = radius * math.sin(time_offset)
                lon_offset = radius * math.sin(time_offset * 2)
                speed = 10.0 + 4 * math.cos(time_offset * 0.7)
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
            await asyncio.sleep(0.1)  # 100ms intervals for smoother animation
        
        await protocol.stop()
    
    async def run_visual_demo(self, duration: int = 30) -> None:
        """Run the visual V2V communication demo."""
        print("🚗 Starting Visual V2V Communication Demo")
        print("=" * 50)
        print("This demo shows:")
        print("• Vehicle positions and movement patterns")
        print("• Communication ranges (dashed circles)")
        print("• Real-time V2V message exchange")
        print("• Proximity detection and data sharing")
        print("=" * 50)
        
        # Create vehicles with realistic starting positions
        vehicles = [
            ("vehicle_001", Position(latitude=37.7749, longitude=-122.4194)),  # Downtown
            ("vehicle_002", Position(latitude=37.7849, longitude=-122.4094)),  # Union Square
            ("vehicle_003", Position(latitude=37.7649, longitude=-122.4294)),  # Mission District
        ]
        
        for vehicle_id, position in vehicles:
            self.create_vehicle(vehicle_id, position)
            self._current_positions[vehicle_id] = position
        
        # Start proximity monitoring
        await self.proximity_detector.start_proximity_monitoring()
        
        # Start vehicle simulations
        tasks = []
        for vehicle_id, _ in vehicles:
            task = asyncio.create_task(self.simulate_vehicle_movement(vehicle_id, duration))
            tasks.append(task)
        
        print("📊 Starting vehicle simulation...")
        print("The demo will run for 20 seconds...")
        
        # Create a simple text-based progress display
        for i in range(20):
            # Update plot and save frame
            self._update_plot(i)
            
            # Print progress
            print(f"⏰ Time: {i+1}/20 seconds - Vehicles moving and communicating...")
            
            # Wait for simulations to complete
            if i == 0:
                # Start the async tasks
                task_handles = []
                for vehicle_id, _ in vehicles:
                    task = asyncio.create_task(self.simulate_vehicle_movement(vehicle_id, 20))
                    task_handles.append(task)
            
            await asyncio.sleep(1.0)
        
        # Wait for all tasks to complete
        if 'task_handles' in locals():
            await asyncio.gather(*task_handles)
        
        # Stop proximity monitoring
        await self.proximity_detector.stop_proximity_monitoring()
        
        # Save final plot
        plt.savefig('v2v_final_positions.png', dpi=150, bbox_inches='tight')
        
        print("\n✅ Visual demo completed!")
        print("📁 Final positions saved to: v2v_final_positions.png")
        print("📊 Check the saved image to see the final vehicle positions and communication patterns.")


async def main():
    """Main visual demo function."""
    demo = VisualV2VDemo()
    
    try:
        await demo.run_visual_demo(20)  # 20 second demo
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"Demo error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
