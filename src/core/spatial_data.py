"""
Spatial Data Models for V2V Communication System

This module defines data structures for spatial awareness information
including position, velocity, acceleration, and trajectory data.
"""

import math
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel, Field, field_validator
import numpy as np


class VehicleState(Enum):
    """Enumeration of possible vehicle states."""
    STOPPED = "stopped"
    MOVING = "moving"
    ACCELERATING = "accelerating"
    DECELERATING = "decelerating"
    TURNING_LEFT = "turning_left"
    TURNING_RIGHT = "turning_right"
    REVERSING = "reversing"
    EMERGENCY = "emergency"


class MessagePriority(Enum):
    """Message priority levels for V2V communication."""
    EMERGENCY = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


@dataclass
class Position:
    """Represents a 3D position with latitude, longitude, and altitude."""
    
    latitude: float  # Decimal degrees
    longitude: float  # Decimal degrees
    altitude: float = 0.0  # Meters above sea level
    accuracy: float = 1.0  # Position accuracy in meters
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def distance_to(self, other: 'Position') -> float:
        """Calculate distance to another position using Haversine formula."""
        R = 6371000  # Earth's radius in meters
        
        lat1_rad = math.radians(self.latitude)
        lat2_rad = math.radians(other.latitude)
        delta_lat = math.radians(other.latitude - self.latitude)
        delta_lon = math.radians(other.longitude - self.longitude)
        
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def bearing_to(self, other: 'Position') -> float:
        """Calculate bearing (direction) to another position in degrees."""
        lat1_rad = math.radians(self.latitude)
        lat2_rad = math.radians(other.latitude)
        delta_lon = math.radians(other.longitude - self.longitude)
        
        y = math.sin(delta_lon) * math.cos(lat2_rad)
        x = (math.cos(lat1_rad) * math.sin(lat2_rad) - 
             math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon))
        
        bearing = math.atan2(y, x)
        return (math.degrees(bearing) + 360) % 360


@dataclass
class Velocity:
    """Represents vehicle velocity in 3D space."""
    
    speed: float  # Speed in m/s
    heading: float  # Direction in degrees (0-360)
    vertical_speed: float = 0.0  # Vertical speed in m/s
    accuracy: float = 0.1  # Velocity accuracy in m/s
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_vector(self) -> Tuple[float, float, float]:
        """Convert velocity to 3D vector (x, y, z) in m/s."""
        heading_rad = math.radians(self.heading)
        x = self.speed * math.sin(heading_rad)
        y = self.speed * math.cos(heading_rad)
        z = self.vertical_speed
        return (x, y, z)
    
    def magnitude(self) -> float:
        """Calculate velocity magnitude."""
        x, y, z = self.to_vector()
        return math.sqrt(x*x + y*y + z*z)


@dataclass
class Acceleration:
    """Represents vehicle acceleration in 3D space."""
    
    linear_acceleration: float  # Linear acceleration in m/s²
    angular_velocity: float = 0.0  # Angular velocity in rad/s
    lateral_acceleration: float = 0.0  # Lateral acceleration in m/s²
    accuracy: float = 0.1  # Acceleration accuracy in m/s²
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TrajectoryPoint:
    """Represents a single point in a predicted trajectory."""
    
    position: Position
    velocity: Velocity
    acceleration: Acceleration
    confidence: float = 1.0  # Prediction confidence (0.0-1.0)
    time_horizon: float = 0.0  # Time in seconds from current time


@dataclass
class Trajectory:
    """Represents a predicted vehicle trajectory."""
    
    vehicle_id: str
    points: List[TrajectoryPoint] = field(default_factory=list)
    prediction_horizon: float = 5.0  # Prediction horizon in seconds
    confidence: float = 1.0  # Overall trajectory confidence
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def add_point(self, point: TrajectoryPoint) -> None:
        """Add a trajectory point."""
        self.points.append(point)
    
    def get_position_at_time(self, time_offset: float) -> Optional[Position]:
        """Get predicted position at a specific time offset."""
        for point in self.points:
            if abs(point.time_horizon - time_offset) < 0.1:
                return point.position
        return None
    
    def intersects_with(self, other: 'Trajectory', time_window: float = 5.0) -> bool:
        """Check if this trajectory intersects with another within time window."""
        for point1 in self.points:
            if point1.time_horizon > time_window:
                break
            for point2 in other.points:
                if point2.time_horizon > time_window:
                    break
                if point1.position.distance_to(point2.position) < 2.0:  # 2m threshold
                    return True
        return False


@dataclass
class SpatialData:
    """Complete spatial awareness data for a vehicle."""
    
    vehicle_id: str
    position: Position
    velocity: Velocity
    acceleration: Acceleration
    state: VehicleState = VehicleState.MOVING
    trajectory: Optional[Trajectory] = None
    confidence: float = 1.0  # Overall data confidence
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def update_position(self, new_position: Position) -> None:
        """Update vehicle position and recalculate velocity if needed."""
        if hasattr(self, '_last_position') and self._last_position:
            # Calculate velocity from position change
            time_delta = (new_position.timestamp - self._last_position.timestamp).total_seconds()
            if time_delta > 0:
                distance = self._last_position.distance_to(new_position)
                self.velocity.speed = distance / time_delta
                self.velocity.heading = self._last_position.bearing_to(new_position)
                self.velocity.timestamp = new_position.timestamp
        
        self.position = new_position
        self._last_position = new_position
    
    def is_emergency(self) -> bool:
        """Check if vehicle is in emergency state."""
        return self.state == VehicleState.EMERGENCY
    
    def get_communication_priority(self) -> MessagePriority:
        """Get message priority based on vehicle state."""
        if self.is_emergency():
            return MessagePriority.EMERGENCY
        elif self.state in [VehicleState.DECELERATING, VehicleState.TURNING_LEFT, VehicleState.TURNING_RIGHT]:
            return MessagePriority.HIGH
        elif self.state == VehicleState.STOPPED:
            return MessagePriority.LOW
        else:
            return MessagePriority.NORMAL


# Pydantic models for API serialization
class PositionModel(BaseModel):
    """Pydantic model for position data."""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    altitude: float = Field(0.0, description="Altitude in meters")
    accuracy: float = Field(1.0, ge=0, description="Position accuracy in meters")
    timestamp: str = Field(..., description="ISO timestamp")


class VelocityModel(BaseModel):
    """Pydantic model for velocity data."""
    speed: float = Field(..., ge=0, description="Speed in m/s")
    heading: float = Field(..., ge=0, le=360, description="Heading in degrees")
    vertical_speed: float = Field(0.0, description="Vertical speed in m/s")
    accuracy: float = Field(0.1, ge=0, description="Velocity accuracy in m/s")
    timestamp: str = Field(..., description="ISO timestamp")


class SpatialDataModel(BaseModel):
    """Pydantic model for complete spatial data."""
    vehicle_id: str = Field(..., description="Vehicle identifier")
    position: PositionModel = Field(..., description="Vehicle position")
    velocity: VelocityModel = Field(..., description="Vehicle velocity")
    state: str = Field(..., description="Vehicle state")
    confidence: float = Field(..., ge=0, le=1, description="Data confidence")
    timestamp: str = Field(..., description="ISO timestamp")
    
    @field_validator('state')
    @classmethod
    def validate_state(cls, v):
        """Validate vehicle state."""
        valid_states = [state.value for state in VehicleState]
        if v not in valid_states:
            raise ValueError(f'Invalid state. Must be one of: {valid_states}')
        return v


class TrajectoryPointModel(BaseModel):
    """Pydantic model for trajectory point."""
    position: PositionModel = Field(..., description="Predicted position")
    velocity: VelocityModel = Field(..., description="Predicted velocity")
    confidence: float = Field(..., ge=0, le=1, description="Prediction confidence")
    time_horizon: float = Field(..., ge=0, description="Time horizon in seconds")


class TrajectoryModel(BaseModel):
    """Pydantic model for trajectory prediction."""
    vehicle_id: str = Field(..., description="Vehicle identifier")
    points: List[TrajectoryPointModel] = Field(..., description="Trajectory points")
    prediction_horizon: float = Field(..., ge=0, description="Prediction horizon in seconds")
    confidence: float = Field(..., ge=0, le=1, description="Overall trajectory confidence")
    timestamp: str = Field(..., description="ISO timestamp")


# Utility functions
def calculate_collision_risk(vehicle1: SpatialData, vehicle2: SpatialData, 
                           time_horizon: float = 5.0) -> float:
    """Calculate collision risk between two vehicles."""
    if not vehicle1.trajectory or not vehicle2.trajectory:
        return 0.0
    
    if vehicle1.trajectory.intersects_with(vehicle2.trajectory, time_horizon):
        # Calculate minimum distance between trajectories
        min_distance = float('inf')
        for point1 in vehicle1.trajectory.points:
            if point1.time_horizon > time_horizon:
                break
            for point2 in vehicle2.trajectory.points:
                if point2.time_horizon > time_horizon:
                    break
                distance = point1.position.distance_to(point2.position)
                min_distance = min(min_distance, distance)
        
        # Convert distance to risk score (0-1)
        if min_distance < 1.0:  # Very close
            return 1.0
        elif min_distance < 5.0:  # Close
            return 0.8
        elif min_distance < 10.0:  # Moderate
            return 0.5
        else:
            return 0.2
    
    return 0.0


def is_within_communication_range(vehicle1: SpatialData, vehicle2: SpatialData, 
                                max_range: float = 1000.0) -> bool:
    """Check if two vehicles are within communication range."""
    distance = vehicle1.position.distance_to(vehicle2.position)
    return distance <= max_range
