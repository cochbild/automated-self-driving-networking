# V2V Spatial Awareness Communication System

## Project Overview

This project develops a **Vehicle-to-Vehicle (V2V) communication system** for autonomous vehicles to securely share spatial awareness data including position, speed, direction, and trajectory information. The system enables nearby self-driving vehicles to coordinate and make safer driving decisions, especially in congested areas where traditional sensors may have limitations.

## Goals

- **Enhanced Safety**: Make automated driving safer through real-time vehicle coordination
- **Spatial Awareness**: Share critical spatial data (position, speed, direction, trajectory) between nearby vehicles
- **Secure Communication**: Implement robust security protocols for V2V data exchange
- **Proximity-Based Networking**: Only communicate with vehicles within communication range
- **Data Privacy**: Automatically purge data when vehicles move out of range
- **Congested Area Optimization**: Improve safety and efficiency in high-traffic scenarios

## Key Features

- **Real-time V2V Communication**: Direct vehicle-to-vehicle data exchange
- **Spatial Data Sharing**: Position, speed, direction, acceleration, trajectory data
- **Proximity Detection**: Automatic range-based communication management
- **Secure Protocols**: Encrypted communication with authentication
- **Data Lifecycle Management**: Automatic purging of out-of-range vehicle data
- **Traffic Coordination**: Enhanced decision-making for congested scenarios
- **Emergency Broadcasting**: Priority communication for safety-critical situations

## Technology Stack

- **Backend**: Python 3.x with asyncio for concurrent V2V communication
- **Communication Protocols**: 
  - DSRC (Dedicated Short-Range Communications) / IEEE 802.11p
  - C-V2X (Cellular Vehicle-to-Everything)
  - Wi-Fi Direct for peer-to-peer communication
- **Security**: 
  - PKI (Public Key Infrastructure) for vehicle authentication
  - AES encryption for data transmission
  - Digital certificates for vehicle identity verification
- **Data Formats**: 
  - BSM (Basic Safety Message) standard compliance
  - JSON/Protocol Buffers for efficient data serialization
- **AI/ML**: Local models for trajectory prediction and collision avoidance
- **Geospatial**: GPS/GNSS integration for precise positioning
- **Real-time Processing**: Low-latency message processing and decision making

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

# Run main application
python3 main.py
```

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

## Contributing

1. Follow the WSL development environment setup
2. Use `python3` for all Python operations
3. Ensure all scripts and tests run in WSL environment
4. Test each model type thoroughly before implementing new ones
5. Use local models when possible (no remote URLs)

## License

[License information to be added]

## Contact

[Contact information to be added]
