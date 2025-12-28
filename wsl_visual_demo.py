#!/usr/bin/env python3
"""
WSL-Compatible Visual V2V Communication Demo

This script creates a visual representation of the V2V communication system
that works in WSL environments by saving frames and creating an animated GIF.
"""

import asyncio
import logging
import sys
import math
import os
from datetime import datetime, timezone
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for WSL
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Circle, FancyBboxPatch
import numpy as np
from PIL import Image

from src.core.vehicle_identity import VehicleIdentity, VehicleIdentityManager
from src.core.spatial_data import SpatialData, Position, Velocity, Acceleration, VehicleState
from src.communication.security_manager import SecurityManager, SecurityConfig
from src.communication.proximity_detector import ProximityDetector, CommunicationRange
from src.communication.v2v_protocol import V2VProtocol, MessageType, V2VMessage

# Configure logging
logging.basicConfig(level=logging.WARNING)  # Reduce log noise for visual demo
logger = logging.getLogger(__name__)


class WSLVisualV2VDemo:
    """WSL-compatible visual demonstration of V2V communication system."""
    
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
        self._frame_files = []  # Store frame file names
        
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
        
        # Add frame info
        info_text = f"Frame {frame + 1}/20 - V2V Communication Demo"
        self.ax.text(0.02, 0.02, info_text, transform=self.ax.transAxes, 
                    fontsize=10, bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        return list(self.vehicle_markers.values()) + list(self.vehicle_labels.values()) + self.communication_lines
    
    def _save_frame(self, frame_num):
        """Save current frame as an image."""
        self._update_plot(frame_num)
        filename = f"frame_{frame_num:03d}.png"
        self.fig.savefig(filename, dpi=100, bbox_inches='tight')
        self._frame_files.append(filename)
        return filename
    
    def _create_gif(self):
        """Create animated GIF from saved frames."""
        if not self._frame_files:
            return None
        
        # Load all frames
        frames = []
        for filename in self._frame_files:
            if os.path.exists(filename):
                frames.append(Image.open(filename))
        
        if not frames:
            return None
        
        # Create GIF
        gif_filename = "v2v_communication_demo.gif"
        frames[0].save(
            gif_filename,
            save_all=True,
            append_images=frames[1:],
            duration=500,  # 500ms per frame
            loop=0  # Infinite loop
        )
        
        # Clean up frame files
        for filename in self._frame_files:
            if os.path.exists(filename):
                os.remove(filename)
        
        return gif_filename
    
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
            await asyncio.sleep(0.1)  # 100ms intervals for smoother animation
        
        await protocol.stop()
    
    async def run_wsl_visual_demo(self, duration: int = 20) -> None:
        """Run the WSL-compatible visual V2V communication demo."""
        print("🚗 Starting WSL Visual V2V Communication Demo")
        print("=" * 60)
        print("This demo shows:")
        print("• Vehicle positions and movement patterns")
        print("• Communication ranges (dashed circles)")
        print("• Real-time V2V message exchange")
        print("• Proximity detection and data sharing")
        print("• Creates animated GIF for WSL environments")
        print("=" * 60)
        
        # Create vehicles with realistic starting positions
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
        
        print("📊 Generating frames...")
        
        # Start vehicle simulations
        tasks = []
        for vehicle_id, _ in vehicles:
            task = asyncio.create_task(self.simulate_vehicle_movement(vehicle_id, duration))
            tasks.append(task)
        
        # Generate frames every second
        for frame in range(duration):
            print(f"📸 Capturing frame {frame + 1}/{duration}")
            self._save_frame(frame)
            
            # Wait for vehicle updates
            await asyncio.sleep(1.0)
        
        # Wait for simulations to complete
        await asyncio.gather(*tasks)
        
        # Stop proximity monitoring
        await self.proximity_detector.stop_proximity_monitoring()
        
        print("🎬 Creating animated GIF...")
        gif_filename = self._create_gif()
        
        if gif_filename:
            print(f"\n✅ WSL Visual demo completed!")
            print(f"📁 Animated GIF saved to: {gif_filename}")
            print("📊 Open the GIF file to see the vehicle movement and communication!")
        else:
            print("\n❌ Failed to create animated GIF")
        
        # Also save final static image
        plt.savefig('v2v_final_positions.png', dpi=150, bbox_inches='tight')
        print("📁 Final positions also saved to: v2v_final_positions.png")


async def main():
    """Main WSL visual demo function."""
    demo = WSLVisualV2VDemo()
    
    try:
        await demo.run_wsl_visual_demo(20)  # 20 second demo
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"Demo error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


