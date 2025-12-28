"""
Vehicle Identity Management for V2V Communication System

This module handles vehicle identification, authentication, and certificate management
for secure Vehicle-to-Vehicle communication.
"""

import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import BaseModel, Field


@dataclass
class VehicleIdentity:
    """Represents a vehicle's identity and authentication information."""
    
    vehicle_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    manufacturer: str = ""
    model: str = ""
    year: int = 0
    vin: str = ""  # Vehicle Identification Number
    capabilities: Dict[str, bool] = field(default_factory=dict)
    certificate: Optional[bytes] = None
    private_key: Optional[bytes] = None
    public_key: Optional[bytes] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize default capabilities and generate keys if not provided."""
        if not self.capabilities:
            self.capabilities = {
                "v2v_communication": True,
                "emergency_broadcast": True,
                "trajectory_prediction": True,
                "collision_avoidance": True,
                "lane_change_coordination": True,
                "intersection_management": True
            }
        
        if not self.expires_at:
            self.expires_at = self.created_at + timedelta(days=365)
    
    def generate_key_pair(self) -> None:
        """Generate RSA key pair for vehicle authentication."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        
        self.private_key = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_key = private_key.public_key()
        self.public_key = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    
    def create_self_signed_certificate(self) -> None:
        """Create a self-signed certificate for vehicle authentication."""
        if not self.private_key:
            self.generate_key_pair()
        
        private_key = serialization.load_pem_private_key(
            self.private_key, password=None
        )
        
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, self.manufacturer),
            x509.NameAttribute(NameOID.COMMON_NAME, f"Vehicle-{self.vehicle_id}"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            self.expires_at
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(f"vehicle-{self.vehicle_id}.local"),
            ]),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        self.certificate = cert.public_bytes(serialization.Encoding.PEM)
    
    def get_vehicle_hash(self) -> str:
        """Generate a unique hash for vehicle identification."""
        data = f"{self.vehicle_id}:{self.vin}:{self.manufacturer}:{self.model}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def is_certificate_valid(self) -> bool:
        """Check if the vehicle's certificate is still valid."""
        if not self.certificate or not self.expires_at:
            return False
        return datetime.utcnow() < self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert vehicle identity to dictionary for serialization."""
        return {
            "vehicle_id": self.vehicle_id,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "year": self.year,
            "vin": self.vin,
            "capabilities": self.capabilities,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "vehicle_hash": self.get_vehicle_hash()
        }


class VehicleIdentityManager:
    """Manages vehicle identities and authentication for V2V communication."""
    
    def __init__(self):
        self.vehicles: Dict[str, VehicleIdentity] = {}
        self.revoked_vehicles: set = set()
    
    def register_vehicle(self, vehicle: VehicleIdentity) -> str:
        """Register a new vehicle in the system."""
        if not vehicle.certificate:
            vehicle.create_self_signed_certificate()
        
        self.vehicles[vehicle.vehicle_id] = vehicle
        return vehicle.vehicle_id
    
    def get_vehicle(self, vehicle_id: str) -> Optional[VehicleIdentity]:
        """Get vehicle identity by ID."""
        return self.vehicles.get(vehicle_id)
    
    def revoke_vehicle(self, vehicle_id: str) -> bool:
        """Revoke a vehicle's certificate."""
        if vehicle_id in self.vehicles:
            self.revoked_vehicles.add(vehicle_id)
            return True
        return False
    
    def is_vehicle_revoked(self, vehicle_id: str) -> bool:
        """Check if a vehicle's certificate is revoked."""
        return vehicle_id in self.revoked_vehicles
    
    def validate_vehicle(self, vehicle_id: str) -> bool:
        """Validate if a vehicle is authorized to communicate."""
        vehicle = self.get_vehicle(vehicle_id)
        if not vehicle:
            return False
        
        if self.is_vehicle_revoked(vehicle_id):
            return False
        
        return vehicle.is_certificate_valid()
    
    def get_nearby_vehicles(self, vehicle_id: str, max_distance: float = 1000.0) -> Dict[str, VehicleIdentity]:
        """Get vehicles within communication range (placeholder for spatial filtering)."""
        # This will be enhanced with actual spatial proximity detection
        return {vid: vehicle for vid, vehicle in self.vehicles.items() 
                if vid != vehicle_id and self.validate_vehicle(vid)}


# Pydantic models for API serialization
class VehicleIdentityRequest(BaseModel):
    """Request model for vehicle identity registration."""
    manufacturer: str = Field(..., description="Vehicle manufacturer")
    model: str = Field(..., description="Vehicle model")
    year: int = Field(..., ge=1900, le=2030, description="Vehicle year")
    vin: str = Field(..., min_length=17, max_length=17, description="17-character VIN")
    capabilities: Dict[str, bool] = Field(default_factory=dict, description="Vehicle capabilities")


class VehicleIdentityResponse(BaseModel):
    """Response model for vehicle identity information."""
    vehicle_id: str = Field(..., description="Unique vehicle identifier")
    vehicle_hash: str = Field(..., description="Vehicle hash for identification")
    capabilities: Dict[str, bool] = Field(..., description="Vehicle capabilities")
    created_at: str = Field(..., description="Registration timestamp")
    expires_at: str = Field(..., description="Certificate expiration timestamp")
    is_valid: bool = Field(..., description="Whether the vehicle is currently valid")

