"""
Proximity Detection for V2V Communication System

This module handles proximity detection and communication range management
for Vehicle-to-Vehicle communication.
"""

import asyncio
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Set, Optional, Callable, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import logging

from ..core.spatial_data import SpatialData, Position, is_within_communication_range


logger = logging.getLogger(__name__)


@dataclass
class ProximityEvent:
    """Represents a proximity-related event."""
    
    event_type: str  # 'vehicle_entered', 'vehicle_exited', 'vehicle_moved'
    vehicle_id: str
    distance: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict = field(default_factory=dict)


@dataclass
class CommunicationRange:
    """Defines communication range parameters."""
    
    max_range: float = 1000.0  # Maximum communication range in meters
    min_range: float = 10.0    # Minimum communication range in meters
    signal_strength_threshold: float = -80.0  # dBm
    update_interval: float = 0.1  # Update interval in seconds
    purge_delay: float = 30.0  # Delay before purging out-of-range vehicles


class ProximityDetector:
    """Detects and manages vehicle proximity for V2V communication."""
    
    def __init__(self, communication_range: Optional[CommunicationRange] = None):
        self.communication_range = communication_range or CommunicationRange()
        self.vehicle_positions: Dict[str, SpatialData] = {}
        self.nearby_vehicles: Dict[str, Set[str]] = defaultdict(set)  # vehicle_id -> set of nearby vehicle_ids
        self.vehicle_last_seen: Dict[str, datetime] = {}
        self.event_callbacks: List[Callable[[ProximityEvent], None]] = []
        self._running = False
        self._update_task: Optional[asyncio.Task] = None
        
    def add_event_callback(self, callback: Callable[[ProximityEvent], None]) -> None:
        """Add a callback function for proximity events."""
        self.event_callbacks.append(callback)
    
    def remove_event_callback(self, callback: Callable[[ProximityEvent], None]) -> None:
        """Remove a callback function."""
        if callback in self.event_callbacks:
            self.event_callbacks.remove(callback)
    
    def _notify_event(self, event: ProximityEvent) -> None:
        """Notify all registered callbacks of a proximity event."""
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in proximity event callback: {e}")
    
    def update_vehicle_position(self, spatial_data: SpatialData) -> None:
        """Update vehicle position and detect proximity changes."""
        vehicle_id = spatial_data.vehicle_id
        previous_position = self.vehicle_positions.get(vehicle_id)
        
        # Update vehicle data
        self.vehicle_positions[vehicle_id] = spatial_data
        self.vehicle_last_seen[vehicle_id] = datetime.now(timezone.utc)
        
        # Detect proximity changes
        if previous_position:
            self._detect_proximity_changes(vehicle_id, previous_position, spatial_data)
        else:
            # New vehicle - check against all existing vehicles
            self._check_new_vehicle_proximity(vehicle_id, spatial_data)
    
    def _detect_proximity_changes(self, vehicle_id: str, 
                                previous_data: SpatialData, 
                                current_data: SpatialData) -> None:
        """Detect changes in vehicle proximity."""
        previous_nearby = self.nearby_vehicles[vehicle_id].copy()
        current_nearby = set()
        
        # Check proximity with all other vehicles
        for other_id, other_data in self.vehicle_positions.items():
            if other_id == vehicle_id:
                continue
                
            if is_within_communication_range(current_data, other_data, 
                                           self.communication_range.max_range):
                current_nearby.add(other_id)
                
                # Check if this is a new proximity
                if other_id not in previous_nearby:
                    event = ProximityEvent(
                        event_type='vehicle_entered',
                        vehicle_id=other_id,
                        distance=current_data.position.distance_to(other_data.position),
                        metadata={'target_vehicle': vehicle_id}
                    )
                    self._notify_event(event)
        
        # Check for vehicles that moved out of range
        for other_id in previous_nearby:
            if other_id not in current_nearby:
                event = ProximityEvent(
                    event_type='vehicle_exited',
                    vehicle_id=other_id,
                    distance=self.communication_range.max_range,
                    metadata={'target_vehicle': vehicle_id}
                )
                self._notify_event(event)
        
        # Update nearby vehicles
        self.nearby_vehicles[vehicle_id] = current_nearby
        
        # Notify of vehicle movement if significant
        distance_moved = previous_data.position.distance_to(current_data.position)
        if distance_moved > 5.0:  # 5 meter threshold
            event = ProximityEvent(
                event_type='vehicle_moved',
                vehicle_id=vehicle_id,
                distance=distance_moved,
                metadata={'previous_position': previous_data.position, 
                         'current_position': current_data.position}
            )
            self._notify_event(event)
    
    def _check_new_vehicle_proximity(self, vehicle_id: str, spatial_data: SpatialData) -> None:
        """Check proximity for a newly added vehicle."""
        nearby = set()
        
        for other_id, other_data in self.vehicle_positions.items():
            if other_id == vehicle_id:
                continue
                
            if is_within_communication_range(spatial_data, other_data, 
                                           self.communication_range.max_range):
                nearby.add(other_id)
                
                # Notify other vehicle of new nearby vehicle
                event = ProximityEvent(
                    event_type='vehicle_entered',
                    vehicle_id=vehicle_id,
                    distance=spatial_data.position.distance_to(other_data.position),
                    metadata={'target_vehicle': other_id}
                )
                self._notify_event(event)
                
                # Also add this vehicle to the other vehicle's nearby list
                if other_id in self.nearby_vehicles:
                    self.nearby_vehicles[other_id].add(vehicle_id)
                else:
                    self.nearby_vehicles[other_id] = {vehicle_id}
        
        self.nearby_vehicles[vehicle_id] = nearby
    
    def get_nearby_vehicles(self, vehicle_id: str) -> List[str]:
        """Get list of vehicles within communication range."""
        return list(self.nearby_vehicles.get(vehicle_id, set()))
    
    def get_vehicle_distance(self, vehicle1_id: str, vehicle2_id: str) -> Optional[float]:
        """Get distance between two vehicles."""
        vehicle1 = self.vehicle_positions.get(vehicle1_id)
        vehicle2 = self.vehicle_positions.get(vehicle2_id)
        
        if vehicle1 and vehicle2:
            return vehicle1.position.distance_to(vehicle2.position)
        return None
    
    def is_vehicle_nearby(self, vehicle1_id: str, vehicle2_id: str) -> bool:
        """Check if two vehicles are within communication range."""
        return vehicle2_id in self.nearby_vehicles.get(vehicle1_id, set())
    
    def remove_vehicle(self, vehicle_id: str) -> None:
        """Remove a vehicle from proximity tracking."""
        if vehicle_id in self.vehicle_positions:
            # Notify other vehicles that this vehicle is leaving
            for other_id in self.nearby_vehicles[vehicle_id]:
                event = ProximityEvent(
                    event_type='vehicle_exited',
                    vehicle_id=vehicle_id,
                    distance=self.communication_range.max_range,
                    metadata={'target_vehicle': other_id}
                )
                self._notify_event(event)
            
            # Clean up data
            del self.vehicle_positions[vehicle_id]
            del self.nearby_vehicles[vehicle_id]
            if vehicle_id in self.vehicle_last_seen:
                del self.vehicle_last_seen[vehicle_id]
    
    async def start_proximity_monitoring(self) -> None:
        """Start the proximity monitoring task."""
        if self._running:
            return
        
        self._running = True
        self._update_task = asyncio.create_task(self._proximity_update_loop())
        logger.info("Proximity monitoring started")
    
    async def stop_proximity_monitoring(self) -> None:
        """Stop the proximity monitoring task."""
        self._running = False
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        logger.info("Proximity monitoring stopped")
    
    async def _proximity_update_loop(self) -> None:
        """Main proximity monitoring loop."""
        while self._running:
            try:
                await self._purge_stale_vehicles()
                await asyncio.sleep(self.communication_range.update_interval)
            except Exception as e:
                logger.error(f"Error in proximity update loop: {e}")
                await asyncio.sleep(1.0)
    
    async def _purge_stale_vehicles(self) -> None:
        """Remove vehicles that haven't been seen for too long."""
        current_time = datetime.now(timezone.utc)
        stale_vehicles = []
        
        for vehicle_id, last_seen in self.vehicle_last_seen.items():
            if (current_time - last_seen).total_seconds() > self.communication_range.purge_delay:
                stale_vehicles.append(vehicle_id)
        
        for vehicle_id in stale_vehicles:
            logger.info(f"Purging stale vehicle: {vehicle_id}")
            self.remove_vehicle(vehicle_id)
    
    def get_communication_statistics(self) -> Dict:
        """Get statistics about current communication state."""
        total_vehicles = len(self.vehicle_positions)
        active_connections = sum(len(nearby) for nearby in self.nearby_vehicles.values()) // 2
        
        return {
            'total_vehicles': total_vehicles,
            'active_connections': active_connections,
            'communication_range': self.communication_range.max_range,
            'update_interval': self.communication_range.update_interval,
            'purge_delay': self.communication_range.purge_delay
        }


class ProximityManager:
    """Manages multiple proximity detectors for different communication ranges."""
    
    def __init__(self):
        self.detectors: Dict[str, ProximityDetector] = {}
        self.default_range = CommunicationRange()
    
    def create_detector(self, name: str, communication_range: Optional[CommunicationRange] = None) -> ProximityDetector:
        """Create a new proximity detector."""
        detector = ProximityDetector(communication_range or self.default_range)
        self.detectors[name] = detector
        return detector
    
    def get_detector(self, name: str) -> Optional[ProximityDetector]:
        """Get a proximity detector by name."""
        return self.detectors.get(name)
    
    def remove_detector(self, name: str) -> bool:
        """Remove a proximity detector."""
        if name in self.detectors:
            del self.detectors[name]
            return True
        return False
    
    async def start_all_detectors(self) -> None:
        """Start all proximity detectors."""
        tasks = []
        for detector in self.detectors.values():
            tasks.append(detector.start_proximity_monitoring())
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop_all_detectors(self) -> None:
        """Stop all proximity detectors."""
        tasks = []
        for detector in self.detectors.values():
            tasks.append(detector.stop_proximity_monitoring())
        await asyncio.gather(*tasks, return_exceptions=True)
