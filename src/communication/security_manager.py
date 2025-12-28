"""
Security Manager for V2V Communication System

This module handles encryption, authentication, and security for Vehicle-to-Vehicle
communication including message signing, verification, and key management.
"""

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any, Tuple, List
from dataclasses import dataclass, field
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import secrets
import logging

from ..core.vehicle_identity import VehicleIdentity

logger = logging.getLogger(__name__)


@dataclass
class SecurityConfig:
    """Configuration for security parameters."""
    
    # Encryption settings
    encryption_algorithm: str = "AES-256-GCM"
    key_size: int = 256
    iv_size: int = 12  # For GCM mode
    
    # Authentication settings
    signature_algorithm: str = "RSA-PSS"
    hash_algorithm: str = "SHA-256"
    
    # Key management
    key_rotation_interval: int = 3600  # 1 hour in seconds
    max_key_age: int = 86400  # 24 hours in seconds
    
    # Message security
    max_message_age: int = 300  # 5 minutes in seconds
    require_timestamp: bool = True
    require_signature: bool = True


@dataclass
class EncryptedMessage:
    """Represents an encrypted V2V message."""
    
    encrypted_data: bytes
    iv: bytes
    signature: bytes
    sender_id: str
    timestamp: datetime
    message_type: str
    priority: int = 3  # Default normal priority
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for transmission."""
        return {
            'encrypted_data': self.encrypted_data.hex(),
            'iv': self.iv.hex(),
            'signature': self.signature.hex(),
            'sender_id': self.sender_id,
            'timestamp': self.timestamp.isoformat(),
            'message_type': self.message_type,
            'priority': self.priority
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EncryptedMessage':
        """Create from dictionary."""
        return cls(
            encrypted_data=bytes.fromhex(data['encrypted_data']),
            iv=bytes.fromhex(data['iv']),
            signature=bytes.fromhex(data['signature']),
            sender_id=data['sender_id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            message_type=data['message_type'],
            priority=data.get('priority', 3)
        )


class SecurityManager:
    """Manages security operations for V2V communication."""
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self.vehicle_identities: Dict[str, VehicleIdentity] = {}
        self.session_keys: Dict[str, Dict[str, bytes]] = {}  # vehicle_id -> {other_vehicle_id: key}
        self.key_timestamps: Dict[str, Dict[str, datetime]] = {}  # vehicle_id -> {other_vehicle_id: timestamp}
        self.revoked_vehicles: set = set()
        
    def register_vehicle(self, vehicle: VehicleIdentity) -> bool:
        """Register a vehicle for secure communication."""
        try:
            if not vehicle.certificate or not vehicle.private_key:
                vehicle.create_self_signed_certificate()
            
            self.vehicle_identities[vehicle.vehicle_id] = vehicle
            self.session_keys[vehicle.vehicle_id] = {}
            self.key_timestamps[vehicle.vehicle_id] = {}
            
            logger.info(f"Registered vehicle: {vehicle.vehicle_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to register vehicle {vehicle.vehicle_id}: {e}")
            return False
    
    def revoke_vehicle(self, vehicle_id: str) -> bool:
        """Revoke a vehicle's communication privileges."""
        if vehicle_id in self.vehicle_identities:
            self.revoked_vehicles.add(vehicle_id)
            # Clean up session keys
            if vehicle_id in self.session_keys:
                del self.session_keys[vehicle_id]
            if vehicle_id in self.key_timestamps:
                del self.key_timestamps[vehicle_id]
            
            # Remove from other vehicles' session keys
            for other_vehicle_id in self.session_keys:
                if vehicle_id in self.session_keys[other_vehicle_id]:
                    del self.session_keys[other_vehicle_id][vehicle_id]
                if vehicle_id in self.key_timestamps[other_vehicle_id]:
                    del self.key_timestamps[other_vehicle_id][vehicle_id]
            
            logger.info(f"Revoked vehicle: {vehicle_id}")
            return True
        return False
    
    def is_vehicle_authorized(self, vehicle_id: str) -> bool:
        """Check if a vehicle is authorized to communicate."""
        return (vehicle_id in self.vehicle_identities and 
                vehicle_id not in self.revoked_vehicles and
                self.vehicle_identities[vehicle_id].is_certificate_valid())
    
    def _generate_session_key(self, vehicle1_id: str, vehicle2_id: str) -> bytes:
        """Generate a session key for communication between two vehicles."""
        # Use ECDH or similar key agreement in production
        # For now, use a deterministic key based on vehicle IDs and timestamp
        key_material = f"{vehicle1_id}:{vehicle2_id}:{int(time.time())}"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.config.key_size // 8,
            salt=b'v2v_salt',  # In production, use random salt
            iterations=100000,
        )
        return kdf.derive(key_material.encode())
    
    def _get_or_create_session_key(self, sender_id: str, receiver_id: str) -> bytes:
        """Get existing session key or create a new one."""
        # Ensure both vehicles are registered
        if not self.is_vehicle_authorized(sender_id) or not self.is_vehicle_authorized(receiver_id):
            raise ValueError("Unauthorized vehicle")
        
        # Check if we have a valid session key
        if (sender_id in self.session_keys and 
            receiver_id in self.session_keys[sender_id] and
            sender_id in self.key_timestamps and
            receiver_id in self.key_timestamps[sender_id]):
            
            key_age = (datetime.now(timezone.utc) - 
                      self.key_timestamps[sender_id][receiver_id]).total_seconds()
            
            if key_age < self.config.max_key_age:
                return self.session_keys[sender_id][receiver_id]
        
        # Generate new session key
        session_key = self._generate_session_key(sender_id, receiver_id)
        
        # Store for both directions
        if sender_id not in self.session_keys:
            self.session_keys[sender_id] = {}
        if sender_id not in self.key_timestamps:
            self.key_timestamps[sender_id] = {}
        
        self.session_keys[sender_id][receiver_id] = session_key
        self.key_timestamps[sender_id][receiver_id] = datetime.now(timezone.utc)
        
        # Store reverse direction
        if receiver_id not in self.session_keys:
            self.session_keys[receiver_id] = {}
        if receiver_id not in self.key_timestamps:
            self.key_timestamps[receiver_id] = {}
        
        self.session_keys[receiver_id][sender_id] = session_key
        self.key_timestamps[receiver_id][sender_id] = datetime.now(timezone.utc)
        
        return session_key
    
    def encrypt_message(self, message_data: Dict[str, Any], 
                       sender_id: str, receiver_id: str,
                       message_type: str = "spatial_data",
                       priority: int = 3) -> EncryptedMessage:
        """Encrypt a message for V2V communication."""
        if not self.is_vehicle_authorized(sender_id):
            raise ValueError(f"Unauthorized sender: {sender_id}")
        
        # Get session key
        session_key = self._get_or_create_session_key(sender_id, receiver_id)
        
        # Serialize message data
        message_json = json.dumps(message_data, default=str).encode('utf-8')
        
        # Generate random IV
        iv = secrets.token_bytes(self.config.iv_size)
        
        # Encrypt message
        cipher = Cipher(
            algorithms.AES(session_key),
            modes.GCM(iv)
        )
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(message_json) + encryptor.finalize()
        
        # Create message to sign
        message_to_sign = {
            'encrypted_data': encrypted_data.hex(),
            'iv': iv.hex(),
            'sender_id': sender_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'message_type': message_type,
            'priority': priority
        }
        
        # Sign message
        signature = self._sign_message(message_to_sign, sender_id)
        
        return EncryptedMessage(
            encrypted_data=encrypted_data,
            iv=iv,
            signature=signature,
            sender_id=sender_id,
            timestamp=datetime.now(timezone.utc),
            message_type=message_type,
            priority=priority
        )
    
    def decrypt_message(self, encrypted_message: EncryptedMessage, 
                       receiver_id: str) -> Dict[str, Any]:
        """Decrypt and verify a V2V message."""
        if not self.is_vehicle_authorized(receiver_id):
            raise ValueError(f"Unauthorized receiver: {receiver_id}")
        
        # Verify message age
        if self.config.require_timestamp:
            message_age = (datetime.now(timezone.utc) - encrypted_message.timestamp).total_seconds()
            if message_age > self.config.max_message_age:
                raise ValueError("Message too old")
        
        # Verify signature
        if self.config.require_signature:
            message_to_verify = {
                'encrypted_data': encrypted_message.encrypted_data.hex(),
                'iv': encrypted_message.iv.hex(),
                'sender_id': encrypted_message.sender_id,
                'timestamp': encrypted_message.timestamp.isoformat(),
                'message_type': encrypted_message.message_type,
                'priority': encrypted_message.priority
            }
            
            if not self._verify_signature(message_to_verify, encrypted_message.signature, 
                                       encrypted_message.sender_id):
                raise ValueError("Invalid signature")
        
        # Get session key
        session_key = self._get_or_create_session_key(encrypted_message.sender_id, receiver_id)
        
        # Decrypt message
        cipher = Cipher(
            algorithms.AES(session_key),
            modes.GCM(encrypted_message.iv)
        )
        decryptor = cipher.decryptor()
        
        try:
            decrypted_data = decryptor.update(encrypted_message.encrypted_data) + decryptor.finalize()
            return json.loads(decrypted_data.decode('utf-8'))
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")
    
    def _sign_message(self, message_data: Dict[str, Any], sender_id: str) -> bytes:
        """Sign a message with the sender's private key."""
        if sender_id not in self.vehicle_identities:
            raise ValueError(f"Unknown sender: {sender_id}")
        
        vehicle = self.vehicle_identities[sender_id]
        if not vehicle.private_key:
            raise ValueError("No private key available")
        
        # Create message hash
        message_json = json.dumps(message_data, sort_keys=True).encode('utf-8')
        message_hash = hashlib.sha256(message_json).digest()
        
        # Sign with private key
        private_key = serialization.load_pem_private_key(
            vehicle.private_key, password=None
        )
        
        signature = private_key.sign(
            message_hash,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return signature
    
    def _verify_signature(self, message_data: Dict[str, Any], 
                         signature: bytes, sender_id: str) -> bool:
        """Verify a message signature."""
        if sender_id not in self.vehicle_identities:
            return False
        
        vehicle = self.vehicle_identities[sender_id]
        if not vehicle.public_key:
            return False
        
        try:
            # Create message hash
            message_json = json.dumps(message_data, sort_keys=True).encode('utf-8')
            message_hash = hashlib.sha256(message_json).digest()
            
            # Verify signature
            public_key = serialization.load_pem_public_key(vehicle.public_key)
            public_key.verify(
                signature,
                message_hash,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            return True
        except Exception as e:
            logger.warning(f"Signature verification failed for {sender_id}: {e}")
            return False
    
    def get_security_statistics(self) -> Dict[str, Any]:
        """Get security statistics."""
        return {
            'registered_vehicles': len(self.vehicle_identities),
            'revoked_vehicles': len(self.revoked_vehicles),
            'active_session_keys': sum(len(keys) for keys in self.session_keys.values()) // 2,
            'encryption_algorithm': self.config.encryption_algorithm,
            'signature_algorithm': self.config.signature_algorithm,
            'max_message_age': self.config.max_message_age,
            'key_rotation_interval': self.config.key_rotation_interval
        }
    
    def cleanup_expired_keys(self) -> int:
        """Clean up expired session keys."""
        current_time = datetime.now(timezone.utc)
        cleaned_count = 0
        
        for vehicle_id in list(self.key_timestamps.keys()):
            for other_vehicle_id in list(self.key_timestamps[vehicle_id].keys()):
                key_age = (current_time - self.key_timestamps[vehicle_id][other_vehicle_id]).total_seconds()
                
                if key_age > self.config.max_key_age:
                    # Remove expired keys
                    if vehicle_id in self.session_keys and other_vehicle_id in self.session_keys[vehicle_id]:
                        del self.session_keys[vehicle_id][other_vehicle_id]
                    if vehicle_id in self.key_timestamps and other_vehicle_id in self.key_timestamps[vehicle_id]:
                        del self.key_timestamps[vehicle_id][other_vehicle_id]
                    cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired session keys")
        
        return cleaned_count

