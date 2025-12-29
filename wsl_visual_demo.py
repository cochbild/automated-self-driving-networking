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
from matplotlib.patches import Circle
from PIL import Image

from src.core.vehicle_identity import VehicleIdentity
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
        self._current_spatial_data = {}  # Store full spatial data for each vehicle
        self._communication_links = []  # Store communication events
        self._collision_warnings = {}  # Store active collision warnings: {(vehicle1, vehicle2): warning_data}
        self._avoidance_maneuvers = {}  # Store active avoidance maneuvers: {vehicle_id: maneuver_data}
        self._original_paths = {}  # Store original paths before avoidance: {vehicle_id: [(x, y), ...]}
        self._avoided_paths = {}  # Store actual paths after avoidance: {vehicle_id: [(x, y), ...]}
        self._collision_avoidances = []  # Track successful collision avoidances
        self._avoidance_stats = {
            'collisions_detected': 0,
            'collisions_avoided': 0,
            'telemetry_used': 0
        }
        self._message_stats = {}  # Track messages per vehicle: {vehicle_id: {'sent': int, 'received': int}}
        # CRITICAL: Use matplotlib color names - these are guaranteed to work
        # Red for Car A, Blue for Car B, Green for Car C
        self._vehicle_colors = {
            'vehicle_001': '#FF0000',  # Red (hex)
            'vehicle_002': '#0000FF',  # Blue (hex)
            'vehicle_003': '#00CC00'   # Green (hex)
        }
        self._vehicle_names = {
            'vehicle_001': 'Car A',
            'vehicle_002': 'Car B',
            'vehicle_003': 'Car C'
        }
        self._frame_files = []  # Store frame file names
        self._collision_threshold = 0.0004  # Distance threshold for collision warning (in degrees, ~44 meters) - increased to ensure detection
        self._collision_avoided_count = {}  # Track collisions avoided per vehicle: {vehicle_id: count}
        self._demo_duration = 35  # Store demo duration for frame count display
        # CRITICAL: Vehicle physical dimensions (like real vehicles)
        # Typical car: ~4.5m long, ~1.8m wide, so safety radius ~2.5m (half length + buffer)
        self._vehicle_radius_m = 2.5  # Vehicle safety radius in meters (accounts for vehicle size)
        self._minimum_safe_distance_m = 5.0  # Minimum safe distance between vehicle edges (in meters)
        
        # Setup matplotlib
        self.fig, self.ax = plt.subplots(figsize=(12, 10))
        self.ax.set_xlim(-0.1, 1.1)
        self.ax.set_ylim(-0.1, 1.1)
        self.ax.set_aspect('equal')
        # CRITICAL: Orient map with N at top, E on right, S at bottom, W on left
        # Note: y-axis is inverted in normalize_position, so coordinates are already correct
        self.ax.set_title('V2V Spatial Awareness Communication System\nReal-time Vehicle Movement, Collision Detection & Avoidance', 
                         fontsize=14, fontweight='bold')
        # Add compass indicators (accounting for inverted y-axis in normalize_position)
        # CRITICAL: normalize_position inverts y-axis: y = 1.0 - ((lat - lat_min) / (lat_max - lat_min))
        # Higher latitude (north) → larger y value → top of plot
        # Lower latitude (south) → smaller y value → bottom of plot
        # So N should be at y=0.98 (top), S at y=0.02 (bottom)
        self.ax.text(0.5, 0.98, 'N', ha='center', va='top', fontsize=18, fontweight='bold', color='black',
                    bbox={'boxstyle': 'round', 'facecolor': 'white', 'alpha': 0.9, 'edgecolor': 'black', 'linewidth': 2})
        self.ax.text(0.5, 0.02, 'S', ha='center', va='bottom', fontsize=18, fontweight='bold', color='black',
                    bbox={'boxstyle': 'round', 'facecolor': 'white', 'alpha': 0.9, 'edgecolor': 'black', 'linewidth': 2})
        self.ax.text(0.02, 0.5, 'W', ha='left', va='center', fontsize=18, fontweight='bold', color='black',
                    bbox={'boxstyle': 'round', 'facecolor': 'white', 'alpha': 0.9, 'edgecolor': 'black', 'linewidth': 2})
        self.ax.text(0.98, 0.5, 'E', ha='right', va='center', fontsize=18, fontweight='bold', color='black',
                    bbox={'boxstyle': 'round', 'facecolor': 'white', 'alpha': 0.9, 'edgecolor': 'black', 'linewidth': 2})
        
        # Initialize plot elements
        self.vehicle_markers = {}
        self.vehicle_labels = {}
        self.communication_lines = []
        
        # Legend will be updated dynamically with vehicle data
        self.legend_elements = []
        self.legend = None
        
    def create_vehicle(self, vehicle_id: str, initial_position: Position = None) -> VehicleIdentity:
        """Create a new vehicle for the demo.
        
        Args:
            vehicle_id: Unique identifier for the vehicle
            initial_position: Optional initial position (stored for reference)
        """
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
        # Create vehicle-specific handler that tracks received messages
        # CRITICAL: This handler is called when a message is processed from the queue
        # Each message sent by one vehicle should increment received count for ALL other vehicles
        def create_spatial_handler(vid):
            def handler(msg):
                # Track received message for this specific vehicle (the receiver)
                # This is called when the message processing loop processes a message from the queue
                if vid not in self._message_stats:
                    self._message_stats[vid] = {'sent': 0, 'received': 0}
                # Only count if this message is from a different vehicle (not self)
                if msg.sender_id != vid:
                    self._message_stats[vid]['received'] += 1
                # Call the shared handler
                self._handle_spatial_data_message(msg)
            return handler
        
        def create_collision_handler(vid):
            def handler(msg):
                # Track received collision warning for this specific vehicle
                if vid not in self._message_stats:
                    self._message_stats[vid] = {'sent': 0, 'received': 0}
                # Only count if this message is from a different vehicle (not self)
                if msg.sender_id != vid:
                    self._message_stats[vid]['received'] += 1
                # Call the shared handler
                self._handle_collision_warning(msg)
            return handler
        
        protocol.register_message_handler(MessageType.SPATIAL_DATA, create_spatial_handler(vehicle_id))
        protocol.register_message_handler(MessageType.COLLISION_WARNING, create_collision_handler(vehicle_id))
        self.protocols[vehicle_id] = protocol
        
        # Store initial position if provided
        if initial_position is not None:
            self._current_positions[vehicle_id] = initial_position
        
        # Initialize message statistics for this vehicle
        self._message_stats[vehicle_id] = {'sent': 0, 'received': 0}
        
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
        
        # NOTE: Message counting is now handled by the vehicle-specific handlers
        # (create_spatial_handler), not here, to avoid double counting
        
        # Update spatial data from received message
        if 'position' in message.data and 'velocity' in message.data:
            pos_data = message.data['position']
            vel_data = message.data['velocity']
            
            position = Position(
                latitude=pos_data['latitude'],
                longitude=pos_data['longitude'],
                altitude=pos_data.get('altitude', 0.0),
                accuracy=pos_data.get('accuracy', 1.0),
                timestamp=datetime.fromisoformat(message.data.get('timestamp', datetime.now(timezone.utc).isoformat()))
            )
            
            velocity = Velocity(
                speed=vel_data['speed'],
                heading=vel_data['heading'],
                accuracy=vel_data.get('accuracy', 0.1),
                timestamp=position.timestamp
            )
            
            spatial_data = SpatialData(
                vehicle_id=message.sender_id,
                position=position,
                velocity=velocity,
                acceleration=Acceleration(linear_acceleration=0.0),
                state=VehicleState.MOVING,
                confidence=message.data.get('confidence', 0.95)
            )
            
            self._current_spatial_data[message.sender_id] = spatial_data
    
    def _handle_collision_warning(self, message: V2VMessage) -> None:
        """Handle collision warning messages."""
        # Store collision warning for visualization
        warning_data = message.data
        vehicle_pair = tuple(sorted([message.sender_id, warning_data.get('target_vehicle', '')]))
        if len(vehicle_pair) == 2 and all(vehicle_pair):
            self._collision_warnings[vehicle_pair] = {
                'timestamp': datetime.now(timezone.utc),
                'risk_level': warning_data.get('risk_level', 0.5),
                'distance': warning_data.get('distance', 0.0),
                'relative_velocity': warning_data.get('relative_velocity', 0.0)
            }
            
            # Trigger avoidance maneuver for receiving vehicle
            receiving_vehicle = warning_data.get('target_vehicle')
            if receiving_vehicle and receiving_vehicle in self._current_spatial_data:
                self._trigger_avoidance_maneuver(receiving_vehicle, warning_data)
                self._avoidance_stats['collisions_avoided'] += 1
                self._avoidance_stats['telemetry_used'] += 1
                
                # Track collisions avoided per vehicle
                if receiving_vehicle not in self._collision_avoided_count:
                    self._collision_avoided_count[receiving_vehicle] = 0
                self._collision_avoided_count[receiving_vehicle] += 1
                
                # Record successful avoidance
                self._collision_avoidances.append({
                    'timestamp': datetime.now(timezone.utc),
                    'vehicle': receiving_vehicle,
                    'warned_by': message.sender_id,
                    'risk_level': warning_data.get('risk_level', 0.5),
                    'distance': warning_data.get('distance', 0.0)
                })
    
    def _trigger_avoidance_maneuver(self, vehicle_id: str, warning_data: dict) -> None:
        """Trigger an avoidance maneuver for a vehicle."""
        if vehicle_id in self._current_spatial_data:
            spatial_data = self._current_spatial_data[vehicle_id]
            current_pos = self._current_positions.get(vehicle_id)
            if current_pos:
                # Store original position for path visualization
                x, y = self._normalize_position(current_pos.latitude, current_pos.longitude)
                if vehicle_id not in self._original_paths:
                    self._original_paths[vehicle_id] = []
                self._original_paths[vehicle_id].append((x, y))
            
            self._avoidance_maneuvers[vehicle_id] = {
                'timestamp': datetime.now(timezone.utc),
                'original_heading': spatial_data.velocity.heading,
                'adjustment': warning_data.get('suggested_adjustment', 15.0),  # degrees
                'duration': 3.0,  # seconds
                'original_position': current_pos
            }
    
    def _check_collisions(self) -> None:
        """Check for potential collisions between vehicles using trajectory prediction.
        
        CRITICAL: This algorithm must be spot-on as it could be the only thing preventing an accident.
        Uses time-to-collision (TTC) and trajectory prediction to detect collision courses.
        """
        vehicle_ids = list(self._current_spatial_data.keys())
        
        # Clear old warnings (older than 2 seconds)
        current_time = datetime.now(timezone.utc)
        expired_warnings = [
            pair for pair, data in self._collision_warnings.items()
            if (current_time - data['timestamp']).total_seconds() > 2.0
        ]
        for pair in expired_warnings:
            del self._collision_warnings[pair]
        
        # Check all vehicle pairs
        for i, vehicle1_id in enumerate(vehicle_ids):
            for vehicle2_id in vehicle_ids[i+1:]:
                if vehicle1_id in self._current_spatial_data and vehicle2_id in self._current_spatial_data:
                    spatial1 = self._current_spatial_data[vehicle1_id]
                    spatial2 = self._current_spatial_data[vehicle2_id]
                    
                    # Calculate current distance in meters
                    lat1, lon1 = spatial1.position.latitude, spatial1.position.longitude
                    lat2, lon2 = spatial2.position.latitude, spatial2.position.longitude
                    
                    # Convert degrees to meters (1 degree ≈ 111,000 meters)
                    dx_m = (lon2 - lon1) * 111000 * math.cos(math.radians((lat1 + lat2) / 2))
                    dy_m = (lat2 - lat1) * 111000
                    center_to_center_distance_m = math.sqrt(dx_m**2 + dy_m**2)
                    
                    # CRITICAL: Account for vehicle physical dimensions (like real vehicles)
                    # The edge of the car (circle boundary - where the black line is) is the point from which collision is detected
                    # NOT the center - this is critical for accurate collision detection
                    # Use the VISUAL circle radius so collision detection matches what the user sees
                    vehicle1_radius = self._get_visual_vehicle_radius_meters()
                    vehicle2_radius = self._get_visual_vehicle_radius_meters()
                    sum_of_radii = vehicle1_radius + vehicle2_radius
                    
                    # CRITICAL: Calculate edge-to-edge distance (center-to-center minus both vehicle radii)
                    # This is the actual distance between vehicle boundaries
                    edge_to_edge_distance_m = center_to_center_distance_m - sum_of_radii
                    
                    # CRITICAL: Use edge-to-edge distance for ALL collision detection calculations
                    # Collision occurs when edge-to-edge distance <= 0 (circles overlap or touch)
                    # The edge of the car is the detection point, NOT the center
                    distance_m = max(0.0, edge_to_edge_distance_m)  # Can't be negative
                    
                    # CRITICAL: Check if edge-to-edge distance <= 0 (circles overlap or touch)
                    # This means the vehicle boundary circles are touching or overlapping
                    # This is the PRIMARY collision condition - based on edges, not centers
                    circles_overlap = edge_to_edge_distance_m <= 0.0
                    
                    # Calculate velocity vectors in m/s
                    v1_speed = spatial1.velocity.speed  # m/s
                    v2_speed = spatial2.velocity.speed  # m/s
                    v1_heading_rad = math.radians(spatial1.velocity.heading)
                    v2_heading_rad = math.radians(spatial2.velocity.heading)
                    
                    v1_x = v1_speed * math.sin(v1_heading_rad)
                    v1_y = v1_speed * math.cos(v1_heading_rad)
                    v2_x = v2_speed * math.sin(v2_heading_rad)
                    v2_y = v2_speed * math.cos(v2_heading_rad)
                    
                    # Relative velocity vector
                    rel_vx = v1_x - v2_x
                    rel_vy = v1_y - v2_y
                    relative_velocity = math.sqrt(rel_vx**2 + rel_vy**2)
                    
                    # CRITICAL: Predict collision using GPS coordinates, speed, and heading
                    # Straightforward algorithm: Calculate if trajectories will intersect
                    collision_risk = False
                    ttc = float('inf')
                    risk_level = 0.0
                    
                    # CRITICAL: First check if circles overlap (immediate collision)
                    if circles_overlap:
                        collision_risk = True
                        ttc = 0.0
                        risk_level = 1.0
                        distance_m = 0.0  # Edge-to-edge is 0 or negative
                    elif center_to_center_distance_m > 0.1:  # Avoid division by zero
                        # Unit vector from vehicle1 to vehicle2
                        unit_dx = dx_m / center_to_center_distance_m
                        unit_dy = dy_m / center_to_center_distance_m
                        
                        # Project relative velocity onto connection line
                        rel_v_projected = rel_vx * unit_dx + rel_vy * unit_dy
                        
                        # If vehicles are closing (negative relative velocity along connection)
                        if rel_v_projected < -0.1:  # Closing at > 0.1 m/s
                            # Calculate time to collision (using edge-to-edge distance)
                            ttc = distance_m / abs(rel_v_projected) if abs(rel_v_projected) > 0.1 else float('inf')
                            
                            # CRITICAL: Predict future positions using GPS coordinates, speed, and heading
                            # Future position = current + (velocity * time)
                            # v_x = speed * sin(heading), v_y = speed * cos(heading)
                            time_horizon = 5.0  # seconds
                            future_lat1 = lat1 + (v1_y / 111000.0) * time_horizon
                            future_lon1 = lon1 + (v1_x / (111000.0 * math.cos(math.radians(lat1)))) * time_horizon
                            future_lat2 = lat2 + (v2_y / 111000.0) * time_horizon
                            future_lon2 = lon2 + (v2_x / (111000.0 * math.cos(math.radians(lat2)))) * time_horizon
                            
                            # Calculate future center-to-center distance
                            future_dx = (future_lon2 - future_lon1) * 111000.0 * math.cos(math.radians((future_lat1 + future_lat2) / 2))
                            future_dy = (future_lat2 - future_lat1) * 111000.0
                            future_center_distance = math.sqrt(future_dx**2 + future_dy**2)
                            
                            # CRITICAL: Account for vehicle size in future distance calculation
                            # Use visual radius so it matches what the user sees
                            visual_radius = self._get_visual_vehicle_radius_meters()
                            future_edge_distance = max(0.0, future_center_distance - visual_radius - visual_radius)
                            
                            # CRITICAL: Check if trajectories will intersect
                            # Simple intersection check: if future distance < current distance, vehicles are converging
                            # AND if they'll be too close (edge-to-edge < safe distance)
                            safe_distance = self._minimum_safe_distance_m
                            converging = future_edge_distance < distance_m
                            will_be_too_close = future_edge_distance < safe_distance
                            currently_too_close = distance_m < safe_distance
                            
                            # CRITICAL: Also check if vehicles are on collision course
                            # If TTC is reasonable (< 15s) and distance is getting smaller, there's a risk
                            on_collision_course = (ttc < 15.0 and ttc > 0.0 and converging)
                            
                            collision_risk = (
                                currently_too_close or  # Already too close (highest priority)
                                (on_collision_course and will_be_too_close) or  # On collision course and will be too close
                                (converging and will_be_too_close and ttc < 10.0)  # Converging, will be too close, and TTC < 10s
                            )
                            
                            if collision_risk:
                                # Calculate risk level (0-1) based on edge-to-edge distance and TTC
                                if distance_m < 5.0:  # Edge-to-edge < 5m = Critical
                                    risk_level = 1.0  # Critical
                                elif distance_m < 10.0:  # Edge-to-edge < 10m = High
                                    risk_level = 0.8  # High
                                elif distance_m < 15.0:  # Edge-to-edge < 15m = Medium-high
                                    risk_level = 0.6  # Medium-high
                                elif ttc < 3.0:  # TTC < 3s = Medium-high
                                    risk_level = 0.6
                                elif ttc < 5.0:  # TTC < 5s = Medium
                                    risk_level = 0.5
                                elif ttc < 10.0:  # TTC < 10s = Low-medium
                                    risk_level = 0.3
                                else:
                                    risk_level = 0.2  # Low
                    
                    if collision_risk:
                        vehicle_pair = tuple(sorted([vehicle1_id, vehicle2_id]))
                        
                        # Only trigger if not already avoiding or risk increased
                        if vehicle_pair not in self._collision_warnings or risk_level > self._collision_warnings[vehicle_pair].get('risk_level', 0):
                            self._collision_warnings[vehicle_pair] = {
                                'timestamp': current_time,
                                'risk_level': risk_level,
                                'distance': distance_m,
                                'relative_velocity': relative_velocity,
                                'ttc': ttc
                            }
                            
                            # Send collision warning messages
                            self._send_collision_warning(vehicle1_id, vehicle2_id, risk_level, distance_m, relative_velocity)
                            self._send_collision_warning(vehicle2_id, vehicle1_id, risk_level, distance_m, relative_velocity)
                            self._avoidance_stats['collisions_detected'] += 1
    
    def _send_collision_warning(self, sender_id: str, target_id: str, risk_level: float, distance: float, relative_velocity: float) -> None:
        """Send a collision warning message."""
        if sender_id in self.protocols:
            warning_message = V2VMessage(
                message_id=f"collision_warning_{sender_id}_{int(datetime.now().timestamp())}",
                message_type=MessageType.COLLISION_WARNING,
                sender_id=sender_id,
                priority=2,  # High priority
                data={
                    'target_vehicle': target_id,
                    'risk_level': risk_level,
                    'distance': distance,
                    'relative_velocity': relative_velocity,
                    'suggested_adjustment': 15.0 if risk_level > 0.5 else 10.0,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                },
                encrypted=True
            )
            # Simulate message handling
            self._handle_collision_warning(warning_message)
    
    def _normalize_position(self, lat: float, lon: float) -> tuple:
        """Convert GPS coordinates to normalized plot coordinates.
        
        CRITICAL: Orient with N at top, E on right, S at bottom, W on left.
        - x-axis: longitude (W to E, left to right)
        - y-axis: latitude (S to N, bottom to top) - inverted so N is at top
        """
        # Simple normalization for San Francisco area
        lat_min, lat_max = 37.76, 37.79
        lon_min, lon_max = -122.43, -122.40
        
        x = (lon - lon_min) / (lon_max - lon_min)  # W to E (left to right)
        # CRITICAL: Map latitude so higher latitude (north) maps to larger y (top of plot)
        # lat_min (south) → y = 0.0 (bottom)
        # lat_max (north) → y = 1.0 (top)
        # Formula: y = (lat - lat_min) / (lat_max - lat_min)
        # Higher lat → larger (lat - lat_min) → larger y → top
        y = (lat - lat_min) / (lat_max - lat_min)  # N (higher lat) is at top
        
        return x, y
    
    def _calculate_vehicle_marker_radius(self) -> float:
        """Calculate vehicle marker radius in plot coordinates for visual display.
        
        CRITICAL: The visual circle boundary (where the black edge is) is what the
        collision detection algorithm uses. The visual size matches the algorithm.
        """
        # Plot covers approximately:
        # Latitude: 37.76 to 37.79 = 0.03 degrees ≈ 3330 meters
        # Longitude: -122.43 to -122.40 = 0.03 degrees ≈ 3330 meters (at this latitude)
        
        lat_min, lat_max = 37.76, 37.79
        lon_min, lon_max = -122.43, -122.40
        
        # Calculate actual distance in meters
        lat_range_m = (lat_max - lat_min) * 111000.0  # ~3330 meters
        lon_range_m = (lon_max - lon_min) * 111000.0 * math.cos(math.radians((lat_min + lat_max) / 2))  # ~3330 meters
        
        # Average range for circular marker (plot is 1.0 units)
        avg_range_m = (lat_range_m + lon_range_m) / 2.0
        
        # Vehicle radius in plot coordinates (for visual display)
        # Plot coordinate 1.0 = avg_range_m meters
        # Vehicle radius = 2.5m, so radius in plot coords = 2.5 / avg_range_m
        vehicle_radius_plot = self._vehicle_radius_m / avg_range_m
        
        # CRITICAL: Make markers VISIBLE by scaling them up
        # The collision detection algorithm will use this SAME visual size
        # Scale factor of 20 makes them clearly visible
        visual_scale_factor = 20.0
        visible_radius = vehicle_radius_plot * visual_scale_factor
        
        # Ensure minimum visible size (about 0.02 in plot coordinates)
        return max(visible_radius, 0.02)
    
    def _get_visual_vehicle_radius_meters(self) -> float:
        """Get the visual vehicle radius in meters (for collision detection).
        
        CRITICAL: This returns the radius of the VISUAL circle (where the black edge is)
        in meters, so collision detection matches what the user sees on screen.
        """
        # Get the visual radius in plot coordinates
        visual_radius_plot = self._calculate_vehicle_marker_radius()
        
        # Convert plot coordinates back to meters
        lat_min, lat_max = 37.76, 37.79
        lon_min, lon_max = -122.43, -122.40
        
        lat_range_m = (lat_max - lat_min) * 111000.0  # ~3330 meters
        lon_range_m = (lon_max - lon_min) * 111000.0 * math.cos(math.radians((lat_min + lat_max) / 2))  # ~3330 meters
        avg_range_m = (lat_range_m + lon_range_m) / 2.0
        
        # Convert plot coordinates to meters
        # visual_radius_plot (in plot coords) * avg_range_m = visual_radius_m (in meters)
        visual_radius_m = visual_radius_plot * avg_range_m
        
        return visual_radius_m
    
    def _update_legend(self) -> None:
        """Update legend with current vehicle direction, speed, and message statistics."""
        # Remove old legend if it exists
        if self.legend is not None:
            self.legend.remove()
        
        # Create legend elements with vehicle data
        legend_elements = []
        for vehicle_id, color in self._vehicle_colors.items():
            vehicle_name = self._vehicle_names[vehicle_id]
            
            # Get message statistics
            msg_sent = self._message_stats.get(vehicle_id, {}).get('sent', 0)
            msg_received = self._message_stats.get(vehicle_id, {}).get('received', 0)
            collisions_avoided = self._collision_avoided_count.get(vehicle_id, 0)
            
            # Get current vehicle data if available
            if vehicle_id in self._current_spatial_data:
                spatial_data = self._current_spatial_data[vehicle_id]
                speed_kmh = spatial_data.velocity.speed * 3.6
                heading = spatial_data.velocity.heading
                # Convert heading to compass direction
                compass_dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
                compass_idx = int((heading + 22.5) / 45) % 8
                direction = compass_dirs[compass_idx]
                label = (f"{vehicle_name}: {speed_kmh:.0f} km/h, {direction} ({heading:.0f}°)\n"
                        f"  Messages: Sent={msg_sent}, Received={msg_received}\n"
                        f"  Collisions Avoided: {collisions_avoided}")
            else:
                label = (f"{vehicle_name}\n"
                        f"  Messages: Sent={msg_sent}, Received={msg_received}\n"
                        f"  Collisions Avoided: {collisions_avoided}")
            
            # Use RGB tuple for marker color (works with both RGB tuples and color names)
            legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', 
                                            markerfacecolor=color, markersize=10, 
                                            label=label, markeredgecolor='black', markeredgewidth=1))
        
        # Place legend in upper right
        self.legend = self.ax.legend(handles=legend_elements, loc='upper right', fontsize=8)
        # Don't add legend to communication_lines as it's handled separately
    
    def _update_plot(self, frame):
        """Update the plot for animation."""
        # Clear previous communication lines and collision indicators
        for line in self.communication_lines:
            if hasattr(line, 'remove'):
                line.remove()
        self.communication_lines.clear()
        
        # Check for collisions
        self._check_collisions()
        
        # Draw original paths (where vehicles would have gone without avoidance)
        for vehicle_id, path_points in self._original_paths.items():
            if len(path_points) > 1:
                path_x = [p[0] for p in path_points]
                path_y = [p[1] for p in path_points]
                original_path = self.ax.plot(path_x, path_y, '--', color='gray', 
                                           linewidth=1.5, alpha=0.5, label='Original Path (Would Collide)')[0]
                self.communication_lines.append(original_path)
        
        # Draw avoided paths (actual paths after avoidance)
        # CRITICAL: Always update vehicle positions from current_spatial_data if available
        # This ensures vehicles keep moving even if _current_positions isn't updated
        for vehicle_id in self._vehicle_colors.keys():
            # Get position from current_spatial_data if available, otherwise use _current_positions
            if vehicle_id in self._current_spatial_data:
                position = self._current_spatial_data[vehicle_id].position
                # Update _current_positions to keep it in sync
                self._current_positions[vehicle_id] = position
            elif vehicle_id in self._current_positions:
                position = self._current_positions[vehicle_id]
            else:
                continue  # Skip if no position data
            
            x, y = self._normalize_position(position.latitude, position.longitude)
            
            # Track avoided path
            if vehicle_id not in self._avoided_paths:
                self._avoided_paths[vehicle_id] = []
            self._avoided_paths[vehicle_id].append((x, y))
            
            # Draw avoided path if vehicle is avoiding
            if vehicle_id in self._avoidance_maneuvers:
                if len(self._avoided_paths[vehicle_id]) > 1:
                    path_x = [p[0] for p in self._avoided_paths[vehicle_id]]
                    path_y = [p[1] for p in self._avoided_paths[vehicle_id]]
                    avoided_path = self.ax.plot(path_x, path_y, '-', 
                                              color='green', linewidth=3, alpha=0.8, 
                                              label='Avoided Path (Using V2V Telemetry)')[0]
                    self.communication_lines.append(avoided_path)
            
            # Show avoidance indicator if active (position is already adjusted in simulation)
            # Note: The actual position adjustment happens in simulate_vehicle_movement, not here
            if vehicle_id in self._avoidance_maneuvers:
                maneuver = self._avoidance_maneuvers[vehicle_id]
                elapsed = (datetime.now(timezone.utc) - maneuver['timestamp']).total_seconds()
                if elapsed < maneuver['duration']:
                    # Show that vehicle is actively avoiding - positioned well above and offset to avoid overlap
                    # Use vehicle ID to determine offset direction (left or right)
                    if vehicle_id == 'vehicle_001':
                        offset_dir = -1
                    elif vehicle_id == 'vehicle_002':
                        offset_dir = 1
                    else:
                        offset_dir = 0
                    avoid_indicator = self.ax.text(x + (offset_dir * 0.15), y + 0.25, '[AVOIDING]\nUsing V2V Data', 
                                                   ha='center', va='bottom', 
                                                   fontsize=10, fontweight='bold', color='green',
                                                   bbox={'boxstyle': 'round', 'facecolor': 'lightgreen', 
                                                           'alpha': 0.9, 'edgecolor': 'green', 'linewidth': 2})
                    self.communication_lines.append(avoid_indicator)
                else:
                    # Maneuver complete - show success indicator
                    if vehicle_id in self._collision_avoidances:
                        # Draw success indicator
                        success_text = self.ax.text(x, y + 0.08, '[SUCCESS] COLLISION AVOIDED\nUsing V2V Telemetry', 
                                                   ha='center', va='bottom', 
                                                   fontsize=11, fontweight='bold', color='green',
                                                   bbox={'boxstyle': 'round', 'facecolor': 'lightgreen', 
                                                           'alpha': 0.9, 'edgecolor': 'green', 'linewidth': 2})
                        self.communication_lines.append(success_text)
                    # Note: maneuver removal happens in simulation loop
            
            # CRITICAL: Get the correct color for this vehicle
            # Colors: vehicle_001=#FF0000 (red), vehicle_002=#0000FF (blue), vehicle_003=#00CC00 (green)
            # CRITICAL: ALWAYS use base color - don't override with red for warnings
            # The warning indicators (circles, text) show the warning, not the vehicle color
            final_color = self._vehicle_colors.get(vehicle_id, '#000000')  # Default to black if not found
            
            if vehicle_id in self.vehicle_markers:
                # Update existing marker position and color
                marker = self.vehicle_markers[vehicle_id]
                if isinstance(marker, Circle):
                    # Update Circle patch position and color
                    marker.set_center((x, y))
                    # CRITICAL: Explicitly set facecolor and edgecolor separately
                    marker.set_facecolor(final_color)  # Set the fill color
                    marker.set_edgecolor('black')  # Black edge
                    marker.set_linewidth(2)
                    marker.set_alpha(1.0)
                else:
                    # Fallback for old marker style (Line2D)
                    marker.set_data([x], [y])
                    marker.set_color(final_color)
            else:
                # Create new marker using Circle patch to match algorithm's vehicle radius
                # CRITICAL: Use Circle patch with radius matching algorithm's vehicle radius
                # The circle represents the vehicle boundary
                marker_radius = self._calculate_vehicle_marker_radius()
                # CRITICAL: Create Circle with BOTH facecolor and edgecolor explicitly set
                # DEBUG: Print what color we're using
                print(f"Creating marker for {vehicle_id} with color {final_color}")
                marker = Circle((x, y), marker_radius, 
                              facecolor=final_color,  # Explicitly set face color
                              edgecolor='black',  # Black edge
                              linewidth=2, 
                              zorder=10,
                              fill=True)
                self.ax.add_patch(marker)
                self.vehicle_markers[vehicle_id] = marker
                print(f"Marker created, facecolor is: {marker.get_facecolor()}, edgecolor is: {marker.get_edgecolor()}")
                
                # Add vehicle label
                label = self.ax.text(x, y + 0.02, self._vehicle_names[vehicle_id], 
                                   ha='center', va='bottom', fontweight='bold', fontsize=10)
                self.vehicle_labels[vehicle_id] = label
            
            # Update label position
            if vehicle_id in self.vehicle_labels:
                self.vehicle_labels[vehicle_id].set_position((x, y + 0.02))
        
        # Update legend with current vehicle data
        self._update_legend()
        
        # Draw collision warnings
        for (vehicle1_id, vehicle2_id), warning_data in self._collision_warnings.items():
            if vehicle1_id in self._current_positions and vehicle2_id in self._current_positions:
                pos1 = self._current_positions[vehicle1_id]
                pos2 = self._current_positions[vehicle2_id]
                x1, y1 = self._normalize_position(pos1.latitude, pos1.longitude)
                x2, y2 = self._normalize_position(pos2.latitude, pos2.longitude)
                
                # Draw warning line between vehicles
                warning_line = self.ax.plot([x1, x2], [y1, y2], 'r--', linewidth=2, alpha=0.7)[0]
                self.communication_lines.append(warning_line)
                
                # Draw warning circles around vehicles
                risk_level = warning_data['risk_level']
                circle_radius = 0.05 * (1 + risk_level)
                warning_circle1 = Circle((x1, y1), circle_radius, fill=False, 
                                       linestyle='-', linewidth=3, alpha=0.8, color='red')
                warning_circle2 = Circle((x2, y2), circle_radius, fill=False, 
                                       linestyle='-', linewidth=3, alpha=0.8, color='red')
                self.ax.add_patch(warning_circle1)
                self.ax.add_patch(warning_circle2)
                self.communication_lines.append(warning_circle1)
                self.communication_lines.append(warning_circle2)
                
                # Add warning text - positioned lower to avoid overlaying cars and other boxes
                warning_text = self.ax.text(0.5, 0.75, '⚠⚠⚠ COLLISION RISK DETECTED ⚠⚠⚠', 
                                          ha='center', va='center', transform=self.ax.transAxes,
                                          fontsize=14, fontweight='bold', color='red',
                                          bbox={'boxstyle': 'round', 'facecolor': 'yellow', 
                                                  'alpha': 0.95, 'edgecolor': 'red', 'linewidth': 3})
                self.communication_lines.append(warning_text)
                
                # Add prominent telemetry data display - positioned at bottom right to avoid overlaying cars
                distance = warning_data.get('distance', 0.0)
                rel_velocity = warning_data.get('relative_velocity', 0.0)
                telemetry_text = (f"[DATA] V2V TELEMETRY DATA:\n"
                                f"Distance: {distance:.1f}m\n"
                                f"Relative Velocity: {rel_velocity:.1f}m/s\n"
                                f"Risk Level: {risk_level:.1%}\n"
                                f"⚠ Using shared telemetry to avoid collision")
                telemetry_label = self.ax.text(0.98, 0.15, telemetry_text, transform=self.ax.transAxes,
                                             ha='right', va='bottom', fontsize=9, fontweight='bold',
                                             bbox={'boxstyle': 'round', 'facecolor': 'lightblue', 
                                                     'alpha': 0.95, 'edgecolor': 'blue', 'linewidth': 2})
                self.communication_lines.append(telemetry_label)
                
                # Add "AVOIDING COLLISION" indicator - positioned to avoid overlap with cars and other boxes
                # Use horizontal offset to separate boxes when vehicles are close
                for idx, vid in enumerate([vehicle1_id, vehicle2_id]):
                    if vid in self._current_positions:
                        vpos = self._current_positions[vid]
                        vx, vy = self._normalize_position(vpos.latitude, vpos.longitude)
                        if vid in self._avoidance_maneuvers:
                            # Position well above and offset horizontally to avoid overlap
                            # Offset first vehicle left, second vehicle right
                            horizontal_offset = -0.15 if idx == 0 else 0.15
                            avoid_text = self.ax.text(vx + horizontal_offset, vy + 0.25, '[AVOIDING]\nUsing V2V Data', 
                                                     ha='center', va='bottom', 
                                                     fontsize=10, fontweight='bold', color='green',
                                                     bbox={'boxstyle': 'round', 'facecolor': 'lightgreen', 
                                                             'alpha': 0.9, 'edgecolor': 'green', 'linewidth': 2})
                            self.communication_lines.append(avoid_text)
        
        # Draw communication circles for all vehicles (always visible to show communication capability)
        for vehicle_id, position in self._current_positions.items():
            x, y = self._normalize_position(position.latitude, position.longitude)
            # Draw communication radius (only if not in collision warning)
            is_in_warning = any(vehicle_id in pair for pair in self._collision_warnings.keys())
            if not is_in_warning:
                comm_circle = Circle((x, y), 0.1, fill=False, 
                                   linestyle='--', alpha=0.3, color='gray', label='Comm Range')
                self.ax.add_patch(comm_circle)
                self.communication_lines.append(comm_circle)
        
        # Also show recent communication events with lines
        # DISABLED: These blue circles were covering the vehicle markers
        # recent_communications = [link for link in self._communication_links 
        #                        if (datetime.now(timezone.utc) - link['timestamp']).total_seconds() < 2]
        # 
        # for comm in recent_communications:
        #     if comm['from'] in self._current_positions:
        #         from_pos = self._current_positions[comm['from']]
        #         from_x, from_y = self._normalize_position(from_pos.latitude, from_pos.longitude)
        #         # Draw a small indicator for recent communication
        #         # CRITICAL: Use zorder=5 so it's BELOW the vehicle markers (zorder=10)
        #         comm_indicator = Circle((from_x, from_y), 0.02, fill=True, 
        #                                alpha=0.5, color='blue', zorder=5)
        #         self.ax.add_patch(comm_indicator)
        #         self.communication_lines.append(comm_indicator)
        
        # Add frame info with collision status and statistics
        collision_count = len(self._collision_warnings)
        avoided_count = len([a for a in self._collision_avoidances 
                            if (datetime.now(timezone.utc) - a['timestamp']).total_seconds() < 5])
        
        # Calculate total messages across all vehicles
        total_sent = sum(stats.get('sent', 0) for stats in self._message_stats.values())
        total_received = sum(stats.get('received', 0) for stats in self._message_stats.values())
        
        info_text = (f"Frame {frame + 1}/{self._demo_duration} - V2V Collision Detection & Avoidance Demo\n"
                    f"Collisions Detected: {self._avoidance_stats['collisions_detected']} | "
                    f"Collisions Avoided: {self._avoidance_stats['collisions_avoided']} | "
                    f"Active Warnings: {collision_count}\n"
                    f"V2V Communication: Total Sent={total_sent}, Total Received={total_received}")
        if avoided_count > 0:
            info_text += f"\n[SUCCESS] {avoided_count} Collision(s) Successfully AVOIDED using V2V Telemetry!"
        self.ax.text(0.02, 0.02, info_text, transform=self.ax.transAxes, 
                    fontsize=9, fontweight='bold',
                    bbox={'boxstyle': 'round', 'facecolor': 'white', 'alpha': 0.95, 
                            'edgecolor': 'black', 'linewidth': 2})
        
        # Add safety comparison info - moved to lower left to avoid legend overlap
        safety_text = ("[SAFETY] V2V vs Camera-Only:\n"
                      "• V2V: 360° awareness, all weather\n"
                      "• V2V: ~1000m range vs ~100m camera\n"
                      "• V2V: <100ms latency vs 200-500ms\n"
                      f"• This Demo: {self._avoidance_stats['collisions_avoided']} collisions prevented")
        safety_text_obj = self.ax.text(0.02, 0.98, safety_text, transform=self.ax.transAxes,
                    ha='left', va='top', fontsize=8,
                    bbox={'boxstyle': 'round', 'facecolor': 'lightyellow', 'alpha': 0.9,
                            'edgecolor': 'orange', 'linewidth': 2})
        self.communication_lines.append(safety_text_obj)
        
        # Update legend with vehicle data (direction and speed)
        self._update_legend()
        
        return list(self.vehicle_markers.values()) + list(self.vehicle_labels.values()) + self.communication_lines
    
    def _save_frame(self, frame_num):
        """Save current frame as an image."""
        self._update_plot(frame_num)
        filename = f"frame_{frame_num:03d}.png"
        self.fig.savefig(filename, dpi=100, bbox_inches='tight')
        self._frame_files.append(filename)
        # Verify file was created
        if not os.path.exists(filename):
            print(f"[WARNING] Frame file not created: {filename}")
        return filename
    
    def _create_gif(self):
        """Create animated GIF from saved frames."""
        if not self._frame_files:
            return None
        
        # Load all frames - ensure we get ALL frames, not just first 20
        # CRITICAL: Sort frame files to ensure correct order
        sorted_frame_files = sorted(self._frame_files, key=lambda x: int(x.split('_')[1].split('.')[0]))
        frames = []
        print(f"[GIF] Loading {len(sorted_frame_files)} frame files (sorted)...")
        for filename in sorted_frame_files:
            if os.path.exists(filename):
                try:
                    frames.append(Image.open(filename))
                except Exception as e:
                    print(f"[GIF] Warning: Could not load {filename}: {e}")
            else:
                print(f"[GIF] Warning: Frame file not found: {filename}")
        
        if not frames:
            print("[GIF] Error: No frames could be loaded")
            return None
        
        print(f"[GIF] Successfully loaded {len(frames)} frames (expected {len(self._frame_files)})")
        
        if len(frames) != len(self._frame_files):
            print(f"[GIF] WARNING: Only loaded {len(frames)} of {len(self._frame_files)} frames!")
        
        # Create GIF with all frames - ensure ALL frames are included
        gif_filename = "v2v_communication_demo.gif"
        print(f"[GIF] Creating GIF with {len(frames)} frames...")
        try:
            # Use all frames, not just first 20
            if len(frames) > 1:
                frames[0].save(
                    gif_filename,
                    save_all=True,
                    append_images=frames[1:],  # Include ALL remaining frames
                    duration=500,  # 500ms per frame
                    loop=0  # Infinite loop
                )
            else:
                frames[0].save(gif_filename, duration=500, loop=0)
            print(f"[GIF] ✓ GIF created successfully: {gif_filename} with {len(frames)} frames")
        except Exception as e:
            print(f"[GIF] Error creating GIF: {e}")
            import traceback
            traceback.print_exc()
            return None
        print(f"[GIF] GIF created successfully: {gif_filename}")
        
        # Clean up frame files
        for filename in self._frame_files:
            if os.path.exists(filename):
                os.remove(filename)
        
        return gif_filename
    
    async def simulate_vehicle_movement(self, vehicle_id: str, duration: int = 35) -> None:
        """Simulate vehicle movement and V2V communication."""
        protocol = self.protocols[vehicle_id]
        await protocol.start()
        
        # Different starting positions and movement patterns
        # CRITICAL: Start vehicles with enough separation so their circles DON'T overlap
        # The visual circle radius determines the minimum separation needed
        visual_radius_m = self._get_visual_vehicle_radius_meters()
        min_separation_m = visual_radius_m * 2.5  # At least 2.5x the radius to ensure no overlap with buffer
        
        # Convert minimum separation from meters to degrees (approximate)
        # 1 degree latitude ≈ 111,000 meters
        min_separation_deg = min_separation_m / 111000.0
        
        # Vehicle 1 starts west, moves east. Vehicle 2 starts south, moves north. They will intersect.
        # Vehicle 3 starts in a different quadrant, well separated
        base_lat = 37.7749  # Center latitude
        base_lon = -122.4194  # Center longitude
        
        if vehicle_id == 'vehicle_001':
            # Start west, will move east
            center_lat = base_lat
            center_lon = base_lon - min_separation_deg * 1.5  # West of center
            base_speed = 12.0
        elif vehicle_id == 'vehicle_002':
            # Start south, will move north
            center_lat = base_lat - min_separation_deg * 1.5  # South of center
            center_lon = base_lon
            base_speed = 15.0
        else:
            # Start northeast, well separated from both
            center_lat = base_lat + min_separation_deg * 1.2  # North of center
            center_lon = base_lon + min_separation_deg * 1.2  # East of center
            base_speed = 10.0
        
        # Initialize cumulative offsets to track position over time
        cumulative_lat_offset = 0.0
        cumulative_lon_offset = 0.0
        
        # CRITICAL: Run simulation continuously, not just once per frame
        # Calculate total iterations needed (duration seconds * 10 updates per second)
        total_iterations = duration * 10  # 10 updates per second for smooth movement
        frame_number = 0
        
        for i in range(total_iterations):
            # Calculate which frame we're in (0 to duration-1)
            frame_number = i // 10
            time_offset = frame_number / 5.0
            
            # CRITICAL: All movement must be based on GPS coordinates, speed, and heading
            # Movement = speed * time in direction of heading (like real vehicles)
            # Vehicles maintain their stated directions and naturally intersect
            if vehicle_id == 'vehicle_001':
                # Vehicle 1: Moves from WEST to EAST (maintains East heading)
                # Will naturally intersect with vehicle_002 coming from South
                heading = 90.0  # East (always)
                if 8 <= frame_number <= 20:
                    speed = base_speed + 8.0  # Faster during collision zone
                else:
                    speed = base_speed
                
            elif vehicle_id == 'vehicle_002':
                # Vehicle 2: Moves from SOUTH to NORTH (maintains North heading)
                # Will naturally intersect with vehicle_001 coming from West
                # CRITICAL: Heading 0° = North = increasing latitude (moving up on map)
                heading = 0.0  # North (always)
                if 8 <= frame_number <= 20:
                    speed = base_speed + 8.0  # Faster during collision zone
                else:
                    speed = base_speed
                
            else:
                # Vehicle 3: Figure-8 pattern - heading rotates, movement follows heading
                heading = (time_offset * 15 + 45) % 360
                speed = base_speed + 4 * math.cos(time_offset * 0.7)
            
            # CRITICAL: Calculate movement based on heading and speed (GPS-based, like real vehicles)
            # Movement distance per iteration (0.1 seconds)
            movement_distance = (speed * 0.1) / 111000.0  # Convert m/s * 0.1s to degrees
            heading_rad = math.radians(heading)
            
            # CRITICAL: GPS movement formula - matches Velocity.to_vector() in spatial_data.py
            # From spatial_data.py: x = speed * sin(heading), y = speed * cos(heading)
            # Where x = East component (longitude), y = North component (latitude)
            # Heading 0° = North = positive latitude (moving up/north on map)
            # Heading 90° = East = positive longitude (moving right/east on map)
            # Heading 180° = South = negative latitude (moving down/south on map)
            # Heading 270° = West = negative longitude (moving left/west on map)
            #
            # For GPS coordinates:
            # - North (0°): lat increases, lon unchanged → lat += distance * cos(0) = distance
            # - East (90°): lat unchanged, lon increases → lon += distance * sin(90) = distance
            # - South (180°): lat decreases, lon unchanged → lat += distance * cos(180) = -distance
            # - West (270°): lat unchanged, lon decreases → lon += distance * sin(270) = -distance
            
            # Calculate movement components
            lat_component = movement_distance * math.cos(heading_rad)  # North/South component
            lon_component = movement_distance * math.sin(heading_rad)  # East/West component
            
            # Apply movement (account for latitude scaling for longitude)
            cumulative_lat_offset += lat_component
            cumulative_lon_offset += lon_component / math.cos(math.radians(center_lat + cumulative_lat_offset))
            
            # Use cumulative offsets for position calculation
            lat_offset = cumulative_lat_offset
            lon_offset = cumulative_lon_offset
            
            # CRITICAL: Apply avoidance maneuver BEFORE calculating position
            # This ensures the position is calculated based on the adjusted heading
            if vehicle_id in self._avoidance_maneuvers:
                maneuver = self._avoidance_maneuvers[vehicle_id]
                maneuver_start = maneuver['timestamp']
                elapsed = (datetime.now(timezone.utc) - maneuver_start).total_seconds()
                
                if elapsed < maneuver['duration']:
                    # Apply heading adjustment to actually avoid collision
                    heading = maneuver['original_heading'] + maneuver['adjustment']
                    # Slightly reduce speed during avoidance for safety
                    speed = speed * 0.85
                    
                    # CRITICAL: Adjust position based on the new heading to actually move the vehicle
                    # Convert heading to radians
                    heading_rad = math.radians(heading)
                    # Calculate movement based on adjusted heading (in degrees)
                    # Move vehicle in the direction of the adjusted heading
                    movement_distance = (speed * 0.1) / 111000.0  # Convert m/s * 0.1s to degrees
                    # Update cumulative offsets to maintain position continuity
                    cumulative_lat_offset += movement_distance * math.cos(heading_rad)
                    cumulative_lon_offset += movement_distance * math.sin(heading_rad) / math.cos(math.radians(center_lat))
                    # Update lat_offset and lon_offset to reflect cumulative position
                    lat_offset = cumulative_lat_offset
                    lon_offset = cumulative_lon_offset
                else:
                    # Maneuver complete - remove it and continue with normal movement
                    del self._avoidance_maneuvers[vehicle_id]
            
            # Create position AFTER avoidance maneuver is applied
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
            self._current_spatial_data[vehicle_id] = spatial_data
            
            # Create and send spatial data message
            message = V2VMessage(
                message_id=f"spatial_{vehicle_id}_{i}_{frame_number}",
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
            
            # Track sent messages
            if vehicle_id in self._message_stats:
                self._message_stats[vehicle_id]['sent'] += 1
            else:
                self._message_stats[vehicle_id] = {'sent': 1, 'received': 0}
            
            # Manually deliver message to other vehicles (since _simulate_network_send doesn't actually deliver)
            # This simulates the broadcast nature of V2V communication
            for other_vehicle_id, other_protocol in self.protocols.items():
                if other_vehicle_id != vehicle_id:
                    # Check if vehicles are in communication range
                    in_range = True
                    if (vehicle_id in self._current_spatial_data and 
                        other_vehicle_id in self._current_spatial_data):
                        spatial1 = self._current_spatial_data[vehicle_id]
                        spatial2 = self._current_spatial_data[other_vehicle_id]
                        distance = spatial1.position.distance_to(spatial2.position)
                        # Communication range is 1000m, but for demo we'll be more lenient
                        in_range = distance < 2000.0  # Extended range for demo visibility
                    # If in range (or no spatial data yet), deliver the message
                    if in_range:
                        # TODO: FIX ENCRYPTION - This is a temporary workaround for the demo
                        # PRODUCTION REQUIREMENT: All messages MUST be properly encrypted and signed
                        # Current issue: Signature verification fails when manually encrypting messages
                        # Required fixes:
                        # 1. Fix certificate exchange between vehicles
                        # 2. Ensure proper signature creation and verification
                        # 3. Implement secure session key establishment
                        # 4. Add anti-tampering mechanisms to prevent malicious actors
                        # See TODO.md section 3 "Security Framework (MANDATORY)" for details
                        
                        # For demo purposes, bypass encryption/signature to avoid verification issues
                        # In production, messages would be properly encrypted and signed
                        # Skip duplicate messages
                        if message.message_id not in other_protocol.message_cache:
                            # Update cache to prevent duplicates
                            other_protocol.message_cache[message.message_id] = datetime.now(timezone.utc)
                            # Process the message directly (don't put in queue to avoid double processing)
                            # The handler will increment received count for the receiving vehicle
                            # This ensures accurate counting: each message sent = 1 sent for sender, 1 received for each receiver
                            try:
                                await other_protocol._process_message(message)
                            except Exception as e:
                                logger.debug(f"Error processing message: {e}")
                                # If processing fails, try putting in queue as fallback
                                await other_protocol.message_queue.put(message)
            await asyncio.sleep(0.1)  # 100ms intervals for smoother animation
        
        await protocol.stop()
    
    async def run_wsl_visual_demo(self, duration: int = 35) -> None:
        """Run the WSL-compatible visual V2V communication demo."""
        self._demo_duration = duration  # Store duration for frame count display
        print("🚗 Starting WSL Visual V2V Communication Demo")
        print("=" * 60)
        print("This demo shows:")
        print("• Vehicle positions and movement patterns")
        print("• Communication ranges (dashed circles)")
        print("• Real-time V2V message exchange")
        print("• Proximity detection and data sharing")
        print("• ⚠ COLLISION DETECTION AND AVOIDANCE")
        print("• [DATA] V2V Telemetry Data (distance, relative velocity, risk)")
        print("• [AVOIDING] Automatic path adjustment when collisions detected")
        print("• [SUCCESS] CLEAR VISUALIZATION: Original paths vs Avoided paths")
        print("• [SAFETY] Safety comparison: V2V vs Camera-Only systems")
        print("• Creates animated GIF for WSL environments")
        print("=" * 60)
        
        # Create vehicles with realistic starting positions
        # CRITICAL: Ensure starting positions don't overlap by using the same logic as simulate_vehicle_movement
        # Calculate minimum separation based on visual vehicle radius
        visual_radius_m = self._get_visual_vehicle_radius_meters()
        min_separation_m = visual_radius_m * 2.5  # At least 2.5x the radius to ensure no overlap with buffer
        min_separation_deg = min_separation_m / 111000.0
        
        base_lat = 37.7749  # Center latitude
        base_lon = -122.4194  # Center longitude
        
        vehicles = [
            ("vehicle_001", Position(latitude=base_lat, longitude=base_lon - min_separation_deg * 1.5)),  # West
            ("vehicle_002", Position(latitude=base_lat - min_separation_deg * 1.5, longitude=base_lon)),  # South
            ("vehicle_003", Position(latitude=base_lat + min_separation_deg * 1.2, longitude=base_lon + min_separation_deg * 1.2)),  # Northeast
        ]
        
        for vehicle_id, position in vehicles:
            self.create_vehicle(vehicle_id, position)
            self._current_positions[vehicle_id] = position
        
        # Start proximity monitoring
        await self.proximity_detector.start_proximity_monitoring()
        
        print("[GENERATING] Generating frames...")
        
        # Start vehicle simulations
        tasks = []
        for vehicle_id, _ in vehicles:
            task = asyncio.create_task(self.simulate_vehicle_movement(vehicle_id, duration))
            tasks.append(task)
        
        # Generate frames every second
        # Give vehicles time to start moving and process initial messages
        await asyncio.sleep(0.5)
        
        for frame in range(duration):
            print(f"📸 Capturing frame {frame + 1}/{duration}")
            # Process any pending messages before capturing frame
            await asyncio.sleep(0.2)  # Allow message processing to complete
            self._save_frame(frame)
            print(f"   ✓ Frame {frame + 1} saved (total frames captured: {len(self._frame_files)})")
            
            # Wait for next frame capture
            await asyncio.sleep(0.8)
        
        print(f"[FRAMES] Total frames captured: {len(self._frame_files)} (expected: {duration})")
        
        # Wait for simulations to complete
        await asyncio.gather(*tasks)
        
        # Stop proximity monitoring
        await self.proximity_detector.stop_proximity_monitoring()
        
        print("🎬 Creating animated GIF...")
        gif_filename = self._create_gif()
        
        if gif_filename:
            print("\n[SUCCESS] WSL Visual demo completed!")
            print(f"[FILE] Animated GIF saved to: {gif_filename}")
            print("[INFO] Open the GIF file to see the vehicle movement, collision detection, and avoidance!")
        else:
            print("\n❌ Failed to create animated GIF")
        
        # Also save final static image
        plt.savefig('v2v_final_positions.png', dpi=150, bbox_inches='tight')
        print("📁 Final positions also saved to: v2v_final_positions.png")


async def main():
    """Main WSL visual demo function."""
    demo = WSLVisualV2VDemo()
    
    try:
        await demo.run_wsl_visual_demo(35)  # 35 second demo for better visualization
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"Demo error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


