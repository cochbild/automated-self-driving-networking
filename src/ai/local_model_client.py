"""
Local Model Client for V2V Communication System

This module provides integration with local AI models (LM Studio) for trajectory
prediction and decision making in the V2V system.
"""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
import numpy as np

from ..core.spatial_data import SpatialData, Trajectory, TrajectoryPoint, Position, Velocity

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for local model client."""
    
    # LM Studio connection settings
    base_url: str = "http://localhost:1234"  # Default LM Studio URL
    api_key: Optional[str] = None
    timeout: float = 30.0
    
    # Model settings
    model_name: str = "trajectory_predictor"
    max_tokens: int = 512
    temperature: float = 0.1  # Low temperature for consistent predictions
    
    # Prediction settings
    prediction_horizon: float = 5.0  # 5 seconds
    prediction_interval: float = 0.5  # 0.5 second intervals
    confidence_threshold: float = 0.7


@dataclass
class TrajectoryPrediction:
    """Result of trajectory prediction."""
    
    vehicle_id: str
    predicted_trajectory: Trajectory
    confidence: float
    prediction_time: datetime
    model_used: str
    processing_time: float


class LocalModelClient:
    """Client for interacting with local AI models via LM Studio."""
    
    def __init__(self, config: Optional[ModelConfig] = None):
        self.config = config or ModelConfig()
        self.session: Optional[aiohttp.ClientSession] = None
        self.connected = False
        self.model_available = False
        
    async def connect(self) -> bool:
        """Connect to the local model server."""
        try:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            )
            
            # Test connection
            async with self.session.get(f"{self.config.base_url}/v1/models") as response:
                if response.status == 200:
                    models = await response.json()
                    self.connected = True
                    self.model_available = len(models.get('data', [])) > 0
                    logger.info(f"Connected to LM Studio. Available models: {len(models.get('data', []))}")
                    return True
                else:
                    logger.error(f"Failed to connect to LM Studio: HTTP {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error connecting to LM Studio: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from the local model server."""
        if self.session:
            await self.session.close()
            self.session = None
        self.connected = False
        self.model_available = False
        logger.info("Disconnected from LM Studio")
    
    async def predict_trajectory(self, spatial_data: SpatialData, 
                               nearby_vehicles: List[SpatialData]) -> Optional[TrajectoryPrediction]:
        """Predict vehicle trajectory using local AI model."""
        if not self.connected or not self.model_available:
            logger.warning("Model not available for trajectory prediction")
            return None
        
        start_time = datetime.now(timezone.utc)
        
        try:
            # Prepare input data for the model
            input_data = self._prepare_trajectory_input(spatial_data, nearby_vehicles)
            
            # Create prompt for trajectory prediction
            prompt = self._create_trajectory_prompt(input_data)
            
            # Call the model
            prediction_result = await self._call_model(prompt)
            
            # Parse the result
            trajectory = self._parse_trajectory_result(prediction_result, spatial_data.vehicle_id)
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            return TrajectoryPrediction(
                vehicle_id=spatial_data.vehicle_id,
                predicted_trajectory=trajectory,
                confidence=prediction_result.get('confidence', 0.8),
                prediction_time=start_time,
                model_used=self.config.model_name,
                processing_time=processing_time
            )
            
        except Exception as e:
            logger.error(f"Error predicting trajectory: {e}")
            return None
    
    async def predict_collision_risk(self, vehicle1: SpatialData, 
                                   vehicle2: SpatialData) -> float:
        """Predict collision risk between two vehicles."""
        if not self.connected or not self.model_available:
            return 0.0
        
        try:
            # Prepare collision risk input
            input_data = {
                'vehicle1': self._spatial_data_to_dict(vehicle1),
                'vehicle2': self._spatial_data_to_dict(vehicle2),
                'distance': vehicle1.position.distance_to(vehicle2.position),
                'relative_velocity': self._calculate_relative_velocity(vehicle1, vehicle2)
            }
            
            # Create prompt for collision risk assessment
            prompt = self._create_collision_risk_prompt(input_data)
            
            # Call the model
            result = await self._call_model(prompt)
            
            # Parse collision risk (0.0 to 1.0)
            risk = float(result.get('collision_risk', 0.0))
            return max(0.0, min(1.0, risk))  # Clamp to [0, 1]
            
        except Exception as e:
            logger.error(f"Error predicting collision risk: {e}")
            return 0.0
    
    async def suggest_maneuver(self, spatial_data: SpatialData, 
                             nearby_vehicles: List[SpatialData],
                             goal: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Suggest a driving maneuver based on current situation."""
        if not self.connected or not self.model_available:
            return None
        
        try:
            # Prepare maneuver input
            input_data = {
                'current_vehicle': self._spatial_data_to_dict(spatial_data),
                'nearby_vehicles': [self._spatial_data_to_dict(v) for v in nearby_vehicles],
                'goal': goal or {}
            }
            
            # Create prompt for maneuver suggestion
            prompt = self._create_maneuver_prompt(input_data)
            
            # Call the model
            result = await self._call_model(prompt)
            
            return {
                'maneuver_type': result.get('maneuver_type', 'maintain_lane'),
                'confidence': result.get('confidence', 0.5),
                'reasoning': result.get('reasoning', ''),
                'parameters': result.get('parameters', {})
            }
            
        except Exception as e:
            logger.error(f"Error suggesting maneuver: {e}")
            return None
    
    async def _call_model(self, prompt: str) -> Dict[str, Any]:
        """Call the local model with a prompt."""
        if not self.session:
            raise RuntimeError("Not connected to model server")
        
        payload = {
            "model": self.config.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an AI assistant specialized in vehicle trajectory prediction and collision avoidance for autonomous vehicles. Provide accurate, safety-focused predictions in JSON format."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": False
        }
        
        async with self.session.post(
            f"{self.config.base_url}/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.config.api_key}"} if self.config.api_key else {}
        ) as response:
            if response.status == 200:
                result = await response.json()
                content = result['choices'][0]['message']['content']
                
                # Try to parse JSON response
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    # If not JSON, return as text
                    return {"response": content}
            else:
                raise RuntimeError(f"Model call failed: HTTP {response.status}")
    
    def _prepare_trajectory_input(self, spatial_data: SpatialData, 
                                nearby_vehicles: List[SpatialData]) -> Dict[str, Any]:
        """Prepare input data for trajectory prediction."""
        return {
            'current_vehicle': self._spatial_data_to_dict(spatial_data),
            'nearby_vehicles': [self._spatial_data_to_dict(v) for v in nearby_vehicles],
            'prediction_horizon': self.config.prediction_horizon,
            'prediction_interval': self.config.prediction_interval
        }
    
    def _spatial_data_to_dict(self, spatial_data: SpatialData) -> Dict[str, Any]:
        """Convert SpatialData to dictionary."""
        return {
            'vehicle_id': spatial_data.vehicle_id,
            'position': {
                'latitude': spatial_data.position.latitude,
                'longitude': spatial_data.position.longitude,
                'altitude': spatial_data.position.altitude,
                'accuracy': spatial_data.position.accuracy
            },
            'velocity': {
                'speed': spatial_data.velocity.speed,
                'heading': spatial_data.velocity.heading,
                'vertical_speed': spatial_data.velocity.vertical_speed,
                'accuracy': spatial_data.velocity.accuracy
            },
            'acceleration': {
                'linear_acceleration': spatial_data.acceleration.linear_acceleration,
                'angular_velocity': spatial_data.acceleration.angular_velocity,
                'lateral_acceleration': spatial_data.acceleration.lateral_acceleration,
                'accuracy': spatial_data.acceleration.accuracy
            },
            'state': spatial_data.state.value,
            'confidence': spatial_data.confidence,
            'timestamp': spatial_data.timestamp.isoformat()
        }
    
    def _create_trajectory_prompt(self, input_data: Dict[str, Any]) -> str:
        """Create a prompt for trajectory prediction."""
        return f"""
Predict the trajectory for vehicle {input_data['current_vehicle']['vehicle_id']} over the next {input_data['prediction_horizon']} seconds.

Current vehicle state:
- Position: {input_data['current_vehicle']['position']}
- Velocity: {input_data['current_vehicle']['velocity']}
- Acceleration: {input_data['current_vehicle']['acceleration']}
- State: {input_data['current_vehicle']['state']}

Nearby vehicles ({len(input_data['nearby_vehicles'])}):
{json.dumps(input_data['nearby_vehicles'], indent=2)}

Please provide a JSON response with:
- trajectory_points: Array of predicted positions, velocities, and timestamps
- confidence: Overall prediction confidence (0.0-1.0)
- reasoning: Brief explanation of the prediction

Each trajectory point should include:
- position: {{latitude, longitude, altitude}}
- velocity: {{speed, heading}}
- time_horizon: seconds from current time
- confidence: point-specific confidence
"""
    
    def _create_collision_risk_prompt(self, input_data: Dict[str, Any]) -> str:
        """Create a prompt for collision risk assessment."""
        return f"""
Assess the collision risk between two vehicles:

Vehicle 1: {input_data['vehicle1']['vehicle_id']}
- Position: {input_data['vehicle1']['position']}
- Velocity: {input_data['vehicle1']['velocity']}

Vehicle 2: {input_data['vehicle2']['vehicle_id']}
- Position: {input_data['vehicle2']['position']}
- Velocity: {input_data['vehicle2']['velocity']}

Distance: {input_data['distance']:.2f} meters
Relative velocity: {input_data['relative_velocity']:.2f} m/s

Please provide a JSON response with:
- collision_risk: Risk score from 0.0 (no risk) to 1.0 (imminent collision)
- time_to_collision: Estimated time to collision in seconds (if applicable)
- reasoning: Brief explanation of the assessment
"""
    
    def _create_maneuver_prompt(self, input_data: Dict[str, Any]) -> str:
        """Create a prompt for maneuver suggestion."""
        return f"""
Suggest a driving maneuver for vehicle {input_data['current_vehicle']['vehicle_id']}:

Current situation:
- Position: {input_data['current_vehicle']['position']}
- Velocity: {input_data['current_vehicle']['velocity']}
- State: {input_data['current_vehicle']['state']}

Nearby vehicles: {len(input_data['nearby_vehicles'])}
Goal: {input_data['goal']}

Please provide a JSON response with:
- maneuver_type: Type of maneuver (maintain_lane, lane_change_left, lane_change_right, accelerate, decelerate, stop, emergency_brake)
- confidence: Confidence in the suggestion (0.0-1.0)
- reasoning: Explanation of why this maneuver is suggested
- parameters: Specific parameters for the maneuver (e.g., target_speed, target_lane)
"""
    
    def _parse_trajectory_result(self, result: Dict[str, Any], vehicle_id: str) -> Trajectory:
        """Parse trajectory prediction result from model."""
        trajectory = Trajectory(
            vehicle_id=vehicle_id,
            prediction_horizon=self.config.prediction_horizon,
            confidence=result.get('confidence', 0.8)
        )
        
        # Parse trajectory points
        points = result.get('trajectory_points', [])
        for i, point_data in enumerate(points):
            position = Position(
                latitude=point_data['position']['latitude'],
                longitude=point_data['position']['longitude'],
                altitude=point_data['position'].get('altitude', 0.0),
                accuracy=point_data['position'].get('accuracy', 1.0)
            )
            
            velocity = Velocity(
                speed=point_data['velocity']['speed'],
                heading=point_data['velocity']['heading'],
                accuracy=point_data['velocity'].get('accuracy', 0.1)
            )
            
            from ..core.spatial_data import Acceleration
            acceleration = Acceleration(
                linear_acceleration=point_data.get('acceleration', {}).get('linear_acceleration', 0.0),
                accuracy=point_data.get('acceleration', {}).get('accuracy', 0.1)
            )
            
            trajectory_point = TrajectoryPoint(
                position=position,
                velocity=velocity,
                acceleration=acceleration,
                confidence=point_data.get('confidence', 0.8),
                time_horizon=point_data.get('time_horizon', i * self.config.prediction_interval)
            )
            
            trajectory.add_point(trajectory_point)
        
        return trajectory
    
    def _calculate_relative_velocity(self, vehicle1: SpatialData, vehicle2: SpatialData) -> float:
        """Calculate relative velocity between two vehicles."""
        # Simple relative velocity calculation
        v1_x, v1_y, _ = vehicle1.velocity.to_vector()
        v2_x, v2_y, _ = vehicle2.velocity.to_vector()
        
        relative_vx = v1_x - v2_x
        relative_vy = v1_y - v2_y
        
        return np.sqrt(relative_vx**2 + relative_vy**2)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check the health of the model connection."""
        if not self.connected:
            return {
                'status': 'disconnected',
                'model_available': False,
                'error': 'Not connected to model server'
            }
        
        try:
            async with self.session.get(f"{self.config.base_url}/health") as response:
                if response.status == 200:
                    return {
                        'status': 'healthy',
                        'model_available': self.model_available,
                        'base_url': self.config.base_url,
                        'model_name': self.config.model_name
                    }
                else:
                    return {
                        'status': 'unhealthy',
                        'model_available': False,
                        'error': f'HTTP {response.status}'
                    }
        except Exception as e:
            return {
                'status': 'error',
                'model_available': False,
                'error': str(e)
            }

