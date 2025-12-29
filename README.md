# V2V Spatial Awareness Communication System

## Research & Innovation Project

**This is a research project designed to foster innovation in secure Vehicle-to-Vehicle (V2V) telemetry communication for autonomous driving systems.** This represents an initial exploration and proof-of-concept for how autonomous vehicles could securely communicate their telemetry data to enhance safety and coordination beyond traditional sensor-based approaches.

### Research Purpose

This project explores how **secure telemetry communication between autonomous vehicles** can:
- Enhance safety beyond camera and sensor limitations
- Enable 360° awareness in all weather conditions
- Provide real-time coordination for collision avoidance
- Demonstrate the viability of V2V technology as a critical safety enhancement

### Important Note on Future Integration

**This is an initial research implementation** exploring the problem space. Any future integration of these features into production autonomous driving systems would require:
1. **Industry Standardization**: Development and adoption of standardized V2V communication protocols
2. **Regulatory Approval**: Compliance with automotive safety standards and regulations
3. **System Integration**: Implementation into each autonomous vehicle manufacturer's systems
4. **Security Certification**: Full security audit and certification of encryption and authentication mechanisms
5. **Interoperability Testing**: Extensive testing across different vehicle manufacturers and systems

This research aims to contribute to the conversation about how autonomous vehicles can communicate securely and safely, moving us toward a future where autonomous driving becomes the standard.

## Project Overview

This project develops a **Vehicle-to-Vehicle (V2V) communication system** for autonomous vehicles to securely share spatial awareness data including position, speed, direction, and trajectory information. The system enables nearby self-driving vehicles to coordinate and make safer driving decisions, especially in congested areas where traditional sensors may have limitations.

**Key Innovation**: This system demonstrates how **secure telemetry sharing** can enhance autonomous vehicle safety beyond camera-only systems, providing 360° awareness, all-weather operation, and extended range communication capabilities.

## Research Goals

This project aims to demonstrate and explore:

- **Enhanced Safety Through Telemetry**: Research how secure telemetry communication can make autonomous driving safer than camera-only systems
- **Spatial Awareness Innovation**: Explore sharing critical spatial data (position, speed, direction, trajectory) between nearby vehicles
- **Secure Communication Research**: Investigate robust security protocols for V2V data exchange that prevent malicious actors
- **Proximity-Based Networking**: Design systems that only communicate with vehicles within communication range
- **Data Privacy**: Explore automatic data purging when vehicles move out of range
- **Safety Enhancement Beyond Sensors**: Demonstrate how V2V telemetry can provide advantages over traditional camera/sensor systems:
  - 360° awareness (vs. limited camera field of view)
  - All-weather operation (vs. camera limitations in poor visibility)
  - Extended range (~1000m vs. ~100m for cameras)
  - Lower latency (<100ms vs. 200-500ms for camera processing)
  - Precise telemetry data (vs. estimated from visual processing)

## Key Research Features

This proof-of-concept demonstrates:

- **Real-time V2V Communication**: Direct vehicle-to-vehicle telemetry data exchange
- **Spatial Data Sharing**: Secure sharing of position, speed, direction, acceleration, and trajectory data
- **Proximity Detection**: Automatic range-based communication management
- **Secure Protocols**: Research into encrypted communication with authentication (see Security Status below)
- **Collision Detection & Avoidance**: Demonstration of how telemetry data enables collision detection and automatic avoidance
- **Data Lifecycle Management**: Automatic purging of out-of-range vehicle data
- **Traffic Coordination**: Enhanced decision-making for congested scenarios
- **Emergency Broadcasting**: Priority communication for safety-critical situations
- **Telemetry-Based Safety**: Proof that V2V telemetry can prevent collisions that camera-only systems might miss

## Research Technology Stack

This research project explores:

- **Backend**: Python 3.x with asyncio for concurrent V2V communication
- **Communication Protocols** (Research Areas): 
  - DSRC (Dedicated Short-Range Communications) / IEEE 802.11p
  - C-V2X (Cellular Vehicle-to-Everything)
  - Wi-Fi Direct for peer-to-peer communication
- **Security Research** (Critical for Production): 
  - PKI (Public Key Infrastructure) for vehicle authentication
  - AES-256-GCM encryption for data transmission (currently being refined)
  - RSA-PSS digital signatures for message integrity (currently being refined)
  - Anti-tampering mechanisms to prevent malicious actors
  - Certificate validation and trust chain verification
  - Message replay attack prevention
- **Data Formats**: 
  - BSM (Basic Safety Message) standard compliance exploration
  - JSON/Protocol Buffers for efficient data serialization
- **AI/ML**: Local models for trajectory prediction and collision avoidance
- **Geospatial**: GPS/GNSS integration for precise positioning
- **Real-time Processing**: Low-latency message processing and decision making

### Security Implementation Status

**Current State**: The demo currently uses a simplified message delivery mechanism for visualization purposes. **For production use, full end-to-end encryption and signature verification must be implemented and certified.** See `TODO.md` Section 3 "Security Framework (MANDATORY)" for detailed requirements and known issues.

## Development Environment

- **OS**: Windows 10/11 with WSL2
- **Shell**: WSL environment for all development operations
- **Python**: Python 3.x (use `python3` command)
- **Engine**: Unreal Engine 5.5.4+ (if applicable for visualization components)

## Getting Started

### Prerequisites

- Windows 10/11 with WSL2 installed
- Python 3.x installed in WSL environment
- Git for version control

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd automated-self-driving-networking
   ```

2. Set up Python virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Project

```bash
# Activate virtual environment
source venv/bin/activate

# Run the visual demo (recommended - shows collision detection and avoidance)
python3 wsl_visual_demo.py

# Or run the basic V2V system
python3 main.py
```

**Note**: `wsl_visual_demo.py` is the main visual demonstration that shows:
- Real-time vehicle movement with collision detection
- Visual representation of V2V communication
- Collision avoidance with before/after path visualization
- Animated GIF output showing the complete demo

## Project Structure

```
v2v-spatial-awareness/
├── README.md
├── TODO.md
├── requirements.txt
├── main.py
├── src/
│   ├── core/
│   │   ├── vehicle_identity.py
│   │   ├── spatial_data.py
│   │   └── message_handler.py
│   ├── communication/
│   │   ├── v2v_protocol.py
│   │   ├── security_manager.py
│   │   └── proximity_detector.py
│   ├── spatial/
│   │   ├── position_tracker.py
│   │   ├── trajectory_predictor.py
│   │   └── collision_avoidance.py
│   ├── ai/
│   │   ├── decision_engine.py
│   │   └── local_models/
│   └── config/
│       ├── security_config.py
│       └── communication_config.py
├── tests/
├── docs/
├── examples/
└── simulation/
    ├── vehicle_simulator.py
    └── traffic_scenarios/
```

## Research Contributions & Future Work

This research project is designed to:
- **Foster Innovation**: Explore new approaches to secure V2V communication
- **Demonstrate Viability**: Show how telemetry-based communication can enhance autonomous vehicle safety
- **Contribute to Standards**: Provide insights that could inform future industry standards
- **Enable Collaboration**: Serve as a foundation for further research and development

### Future Integration Path

For this research to become a production reality, the following would need to occur:

1. **Industry Standardization**
   - Development of standardized V2V communication protocols
   - Agreement on message formats and security requirements
   - Interoperability standards across manufacturers

2. **Regulatory Framework**
   - Regulatory approval for V2V communication systems
   - Compliance with automotive safety standards (ISO 26262, etc.)
   - Privacy and security regulations

3. **Manufacturer Implementation**
   - Integration into each autonomous vehicle manufacturer's systems
   - Hardware requirements (DSRC/C-V2X radios)
   - Software integration with vehicle control systems

4. **Security Certification**
   - Full security audit and penetration testing
   - Certification of encryption and authentication mechanisms
   - Ongoing security monitoring and updates

5. **Testing & Validation**
   - Extensive real-world testing
   - Interoperability testing across manufacturers
   - Safety validation and certification

### Contributing to This Research

1. Follow the WSL development environment setup
2. Use `python3` for all Python operations
3. Ensure all scripts and tests run in WSL environment
4. Test each model type thoroughly before implementing new ones
5. Use local models when possible (no remote URLs)
6. Focus on security research and innovation
7. Document findings and potential improvements

## Research Disclaimer

**This is a research and proof-of-concept project.** The implementations, protocols, and security mechanisms demonstrated here are:
- **Exploratory**: Designed to explore the problem space and potential solutions
- **Educational**: Intended to foster understanding and innovation
- **Not Production-Ready**: Require extensive refinement, testing, and certification before production use
- **Subject to Change**: Will evolve as research progresses and industry standards develop

**Any future production implementation would require:**
- Industry standardization and regulatory approval
- Full security certification and audit
- Integration into manufacturer-specific vehicle systems
- Extensive real-world testing and validation

## Vision: Autonomous Driving as the Future

This research project is part of a broader vision where **autonomous driving becomes the standard**, enabled by:
- Secure vehicle-to-vehicle communication
- Enhanced safety through telemetry sharing
- Coordinated decision-making between vehicles
- Innovation in automotive safety technology

By exploring how vehicles can securely communicate their telemetry data, this research aims to contribute to making autonomous driving safer, more reliable, and ultimately the way of the future.

## License

[License information to be added]

## Contact

[Contact information to be added]
