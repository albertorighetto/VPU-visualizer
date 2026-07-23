# VPU Visualizer 2.0

A desktop application for visualizing VPU (Video Processing Unit) usage on Analog Way Aquilon devices.

## Features

- Real-time VPU usage monitoring
- Screen and layer visualization
- Dark theme UI inspired by official software
- Debug logging for troubleshooting
- Support for multiple device types (RS1-RS6, C, C+, C-Max)

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python main.py
   ```

## Usage

1. Enter the IP address of your Aquilon device (default: 127.0.0.1)
2. Enter the TCP port (default: 10606)
3. Click "Connect" to establish connection
4. View VPU usage in the "VPU Usage" tab
5. View active screens in the "Screens" tab
6. View summary in the "Summary" tab

## API Paths Reference

The application communicates with Aquilon devices using the AWJ protocol. Key API paths:

### Device Information
- `DeviceObject/system/$device/@items/{device_id}/@props/dev` - Device type

### Screen Information
- `DeviceObject/preconfig/resources/new/$screen/@items/S{id}/status/@props/mode` - Screen mode
- `DeviceObject/preconfig/resources/new/$screen/@items/S{id}/status/@props/layerCount` - Layer count
- `DeviceObject/preconfig/resources/new/$screen/@items/S{id}/status/@props/isOptimized` - Optimization status

### VPU Layer Information
- `DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{device_id}/$vpu-layer/@items/PROC_{vpu}_SCALER_{scaler}/@props/isEnabled`
- `DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{device_id}/$vpu-layer/@items/PROC_{vpu}_SCALER_{scaler}/@props/isAvailable`
- `DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{device_id}/$vpu-layer/@items/PROC_{vpu}_SCALER_{scaler}/@props/capability`
- `DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{device_id}/$vpu-layer/@items/PROC_{vpu}_SCALER_{scaler}/@props/usedInScreen`
- `DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{device_id}/$vpu-layer/@items/PROC_{vpu}_SCALER_{scaler}/@props/usedInLayer`

### Scaler Allocation
- `DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{device_id}/$vpu-layer/@items/PROC_{vpu}_SCALER_{scaler}/scaler-allocation/@props/usedOnOutPipe{pipe}`

### Pipe Information
- `DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{device_id}/$pipe/@items/{pipe_id}/@props/isUsed`

## Layer Capabilities

Based on the official software, layer capabilities include:
- OFF - Layer disabled
- DUAL - Dual capability
- 4K - 4K resolution
- 5K - 5K resolution
- 8K - 8K resolution

## Color Scheme

The application uses a dark theme with colors derived from the official software:
- Primary accent: #2e3192
- Highlight: #826bff
- Active status: #8bb650
- Warning: #e6b421
- Error: #cc2e60

## Device Types and VPU Counts

| Device Type | VPU Count |
|-------------|-----------|
| RS1/RSALPHA | 1 |
| RS2/RS3 | 2 |
| RS4/RS5 | 3 |
| RS6 | 4 |
| C | 2 |
| C+ | 3 |
| C-Max | 4 |

## License

This project is for educational and development purposes.
