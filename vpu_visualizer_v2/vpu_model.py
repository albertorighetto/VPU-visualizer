"""
VPU Visualizer 2.0 Data Models
Data structures for devices, VPUs, screens, and scalers.
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum


class LayerCapability(Enum):
    """Layer capability levels based on app source LAYER_CAPABILITIES enum."""
    OFF = "OFF"
    DUAL = "DUAL"
    K4 = "4K"
    K3 = "3"
    K5 = "5K"
    K5_NUM = "5"
    K6 = "6"
    K7 = "7"
    K8 = "8K"


# Note: there's no static device-type -> VPU-count table here on purpose.
# Chassis size varies per unit and isn't reliably inferable from the type
# string alone, so VPU slots are only ever taken from live polling of
# hardware/$card/@items/PROC_n isAvailable (see AWJClient.MAX_PROC_SLOTS and
# MainWindow's hardware-availability chain) - never assumed.

# Human-readable labels for device types, from the firmware's VAR_LABELS.DEV.
DEVICE_LABELS = {
    "NLC_DBG": "AQL DBG",
    "NLC_RS1": "AQL RS1",
    "NLC_RS2": "AQL RS2",
    "NLC_RS3": "AQL RS3",
    "NLC_RS4": "AQL RS4",
    "NLC_C": "AQL C",
    "NLC_CPLUS": "AQL C+",
    "NLC_RSALPHA": "AQL RS alpha",
    "NLC_RS5": "AQL RS5",
    "NLC_RS6": "AQL RS6",
    "NLC_CMAX": "AQL Cmax",
    "VDW_W": "VDW_W",
    "VDW_WPLUS": "VDW_W+",
    "VDW_WMAX": "VDW_WMAX",
    "NLC_CMINI": "AQL Cmini",
}


def get_device_label(device_type: Optional[str]) -> str:
    """Get the human-readable label for a device type, falling back to the raw type."""
    if not device_type:
        return "?"
    return DEVICE_LABELS.get(device_type, device_type)


@dataclass
class Scaler:
    """Represents a single scaler in a VPU."""
    id: int
    is_enabled: Optional[bool] = None
    is_available: Optional[bool] = None
    layer: Optional[int] = None
    capability: Optional[str] = None
    screen: Optional[int] = None
    pipes: Dict[int, Any] = field(default_factory=dict)  # pipe_id -> usage value
    cutnfill_capa: Optional[Any] = None
    seamless_capa: Optional[Any] = None
    channel: Optional[Any] = None
    slice: Optional[Any] = None
    
    def is_complete(self) -> bool:
        """Check if we have all the data for this scaler."""
        return self.is_enabled is not None
    
    def get_pipe_usage_display(self) -> str:
        """Get a display string for pipe usage."""
        used_pipes = [p for p, v in self.pipes.items() if v and v != "NONE"]
        if used_pipes:
            return f"Pipes: {', '.join(map(str, used_pipes))}"
        return "No pipes"


@dataclass
class VPU:
    """Represents a Video Processing Unit."""
    vpu_id: int
    scalers: List[Scaler] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.scalers:
            self.scalers = [Scaler(id=i) for i in range(1, 17)]

    def get_scaler(self, scaler_id: int) -> Optional[Scaler]:
        """Get scaler (mixer) by ID (1-16)."""
        for scaler in self.scalers:
            if scaler.id == scaler_id:
                return scaler
        return None

    def get_active_scalers_count(self) -> int:
        """Count active scalers."""
        return sum(1 for s in self.scalers if s.is_enabled)

    def get_usage_percentage(self) -> float:
        """Get VPU usage as percentage."""
        return (self.get_active_scalers_count() / 16) * 100


@dataclass
class Device:
    """Represents a device (unit) in the system."""
    id: int
    device_type: Optional[str] = None
    vpu_count: int = 0
    vpus: List[VPU] = field(default_factory=list)
    # PROC (VPU hardware card) slot -> isAvailable, from
    # hardware/$card/@items/PROC_n. Keyed independently of `vpus` since this
    # can arrive before or after the device type response.
    hardware_available: Dict[int, bool] = field(default_factory=dict)

    def get_vpu(self, vpu_id: int) -> Optional[VPU]:
        """Get a VPU slot, but only if its hardware has already been
        confirmed present via add_vpu() - never speculatively created."""
        for vpu in self.vpus:
            if vpu.vpu_id == vpu_id:
                return vpu
        return None

    def add_vpu(self, vpu_id: int) -> VPU:
        """Register a VPU slot once hardware/$card/@items/PROC_n has
        confirmed it's available. This is the only source of VPU count -
        there's no static per-device-type table to fall back on."""
        existing = self.get_vpu(vpu_id)
        if existing:
            return existing
        new_vpu = VPU(vpu_id=vpu_id)
        self.vpus.append(new_vpu)
        self.vpus.sort(key=lambda v: v.vpu_id)
        self.vpu_count = max(self.vpu_count, vpu_id)
        return new_vpu

    def update_from_type(self, device_type: str):
        """Update device info from type string. Doesn't touch VPU count/slots -
        those only ever come from live hardware-availability polling."""
        # Remove 'DEV_' prefix if present
        self.device_type = device_type.replace("DEV_", "")


@dataclass 
class Layer:
    """Represents a layer in a screen."""
    id: int
    capability: Optional[str] = None
    regions: List[Any] = field(default_factory=list)
    mask: bool = False


@dataclass
class Screen:
    """Represents a screen."""
    id: int
    active: bool = False
    optimized: bool = False
    is_stereo_3d: bool = False
    region_validity: Optional[List[Any]] = None
    layers: List[Layer] = field(default_factory=list)

    def has_multiple_regions(self) -> bool:
        """Whether this screen is actually split into more than one region
        (regionValidity holds the list of currently valid/active region IDs,
        e.g. ["1", "2", "3"])."""
        try:
            return len(self.region_validity) > 1
        except TypeError:
            return False

    def get_layer(self, layer_id: int) -> Optional[Layer]:
        """Get or create layer by ID."""
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        return None
    
    def add_layer(self, layer_id: int) -> Layer:
        """Add a new layer."""
        layer = Layer(id=layer_id)
        self.layers.append(layer)
        self.layers.sort(key=lambda l: l.id)
        return layer


class VPUModel:
    """Main data model for VPU Visualizer.

    Parses paths for a selectable configuration resource tree ("new" = pending
    config, "current" = running config); messages addressing the other tree
    are ignored so switching config views never mixes data.
    """

    # Device type and hardware card presence are not resource-dependent
    REGEX_DEVICE_TYPE = re.compile(r"DeviceObject/system/\$device/@items/(\d+)/@props/dev")
    REGEX_VPU_HARDWARE_AVAILABLE = re.compile(
        r"DeviceObject/system/\$device/@items/(\d+)/hardware/\$card/@items/PROC_(\d+)/@props/isAvailable")

    def __init__(self, resource: str = "new"):
        self.devices: List[Device] = [Device(id=i) for i in range(1, 5)]
        self.screens: List[Screen] = [Screen(id=i) for i in range(1, 25)]
        self._callbacks: List[callable] = []
        self.version = 0  # bumped on every model change; UI panels poll this
        self.resource = resource
        self._compile_patterns(resource)

    def set_resource(self, resource: str):
        """Switch between the 'new' (pending) and 'current' (running) config trees."""
        self.resource = resource
        self._compile_patterns(resource)

    def _compile_patterns(self, resource: str):
        """(Re)compile all resource-dependent path patterns."""
        res = re.escape(resource)
        screen = rf"DeviceObject/preconfig/resources/{res}/\$screen/@items/S(\d+)"
        # Live AWJ protocol node name is $vpuMixer (the web UI's internal Redux
        # naming uses $vpuLayer, but the device rejects that path)
        mixer = (rf"DeviceObject/preconfig/resources/{res}/status/mapping/\$device"
                 rf"/@items/(\d+)/\$vpuMixer/@items/PROC_(\d+)_MIXER_(\d+)")

        self.REGEX_SCREEN_MODE = re.compile(rf"{screen}/status/@props/mode")
        self.REGEX_SCREEN_LAYER_COUNT = re.compile(rf"{screen}/status/@props/layerCount")
        self.REGEX_SCREEN_OPTIMIZED = re.compile(rf"{screen}/status/@props/isOptimized")
        self.REGEX_SCREEN_STEREO3D = re.compile(rf"{screen}/status/@props/isStereo3d")
        self.REGEX_SCREEN_REGION_VALIDITY = re.compile(rf"{screen}/status/@props/regionValidity")
        self.REGEX_LAYER_CAPABILITY = re.compile(rf"{screen}/\$layer/@items/(\d+)/status/@props/capability")
        self.REGEX_LAYER_REGIONS = re.compile(rf"{screen}/\$layer/@items/(\d+)/status/@props/usedInRegions")
        self.REGEX_LAYER_MASK = re.compile(rf"{screen}/\$layer/@items/(\d+)/status/@props/canUseMask")

        self.REGEX_VPU_ENABLED = re.compile(rf"{mixer}/@props/isEnabled")
        self.REGEX_VPU_AVAILABLE = re.compile(rf"{mixer}/@props/isAvailable")
        self.REGEX_VPU_CAPABILITY = re.compile(rf"{mixer}/@props/capability")
        self.REGEX_VPU_SCREEN = re.compile(rf"{mixer}/@props/usedInScreen")
        self.REGEX_VPU_LAYER = re.compile(rf"{mixer}/@props/usedInLayer")
        self.REGEX_VPU_CUTNFILL_CAPA = re.compile(rf"{mixer}/@props/cutnfillCapa")
        self.REGEX_VPU_SEAMLESS_CAPA = re.compile(rf"{mixer}/@props/seamlessCapa")
        self.REGEX_VPU_CHANNEL = re.compile(rf"{mixer}/@props/channel")
        self.REGEX_VPU_SLICE = re.compile(rf"{mixer}/@props/slice")
        # mixerAllocation, not the web UI's scalerAllocation
        self.REGEX_SCALER_PIPE = re.compile(rf"{mixer}/mixerAllocation/@props/usedOnOutPipe(\d+)")

    def add_update_callback(self, callback: callable):
        """Add a callback to be called when data is updated."""
        self._callbacks.append(callback)

    def _notify_update(self):
        """Notify all callbacks of data update."""
        self.version += 1
        for callback in self._callbacks:
            callback()

    def reset(self):
        """Reset all device, VPU, and screen state to a clean slate."""
        self.devices = [Device(id=i) for i in range(1, 5)]
        self.screens = [Screen(id=i) for i in range(1, 25)]
        self._notify_update()

    def get_device(self, device_id: int) -> Optional[Device]:
        """Get device by ID (1-4)."""
        for device in self.devices:
            if device.id == device_id:
                return device
        return None
    
    def get_screen(self, screen_id: int) -> Optional[Screen]:
        """Get screen by ID (1-24)."""
        for screen in self.screens:
            if screen.id == screen_id:
                return screen
        return None
    
    def process_message(self, data: dict) -> str:
        """
        Process an incoming AWJ message and update the model.
        Returns a debug string describing what was updated.
        """
        if "path" not in data:
            return "[PARSE] No path in message"
        
        path = data["path"]
        value = data.get("value")
        
        # Try each pattern
        result = self._try_parse_device_type(path, value)
        if result: return result

        result = self._try_parse_vpu_hardware_available(path, value)
        if result: return result

        result = self._try_parse_screen_mode(path, value)
        if result: return result
        
        result = self._try_parse_screen_layer_count(path, value)
        if result: return result
        
        result = self._try_parse_screen_optimized(path, value)
        if result: return result

        result = self._try_parse_screen_stereo3d(path, value)
        if result: return result

        result = self._try_parse_screen_region_validity(path, value)
        if result: return result

        result = self._try_parse_layer_capability(path, value)
        if result: return result
        
        result = self._try_parse_layer_regions(path, value)
        if result: return result
        
        result = self._try_parse_layer_mask(path, value)
        if result: return result
        
        result = self._try_parse_vpu_enabled(path, value)
        if result: return result
        
        result = self._try_parse_vpu_available(path, value)
        if result: return result
        
        result = self._try_parse_vpu_capability(path, value)
        if result: return result
        
        result = self._try_parse_vpu_screen(path, value)
        if result: return result
        
        result = self._try_parse_vpu_layer(path, value)
        if result: return result

        result = self._try_parse_vpu_cutnfill_capa(path, value)
        if result: return result

        result = self._try_parse_vpu_seamless_capa(path, value)
        if result: return result

        result = self._try_parse_vpu_channel(path, value)
        if result: return result

        result = self._try_parse_vpu_slice(path, value)
        if result: return result

        result = self._try_parse_scaler_pipe(path, value)
        if result: return result

        return f"[PARSE] Unhandled path: {path}"
    
    def _try_parse_device_type(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_DEVICE_TYPE.match(path)
        if match:
            device_id = int(match.group(1))
            device = self.get_device(device_id)
            if device and value:
                device.update_from_type(value)
                self._notify_update()
                return f"[DEVICE] Device {device_id}: type={device.device_type}, vpus={device.vpu_count}"
        return None

    def _try_parse_vpu_hardware_available(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_VPU_HARDWARE_AVAILABLE.match(path)
        if match:
            device_id = int(match.group(1))
            proc_id = int(match.group(2))
            device = self.get_device(device_id)
            if device:
                available = bool(value)
                device.hardware_available[proc_id] = available
                if available:
                    device.add_vpu(proc_id)
                self._notify_update()
                return f"[HARDWARE] Device {device_id}, PROC_{proc_id}: available={available}"
        return None

    def _try_parse_screen_mode(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_SCREEN_MODE.match(path)
        if match:
            screen_id = int(match.group(1))
            screen = self.get_screen(screen_id)
            if screen:
                screen.active = value != "DISABLED"
                self._notify_update()
                return f"[SCREEN] Screen {screen_id}: active={screen.active}"
        return None
    
    def _try_parse_screen_layer_count(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_SCREEN_LAYER_COUNT.match(path)
        if match:
            screen_id = int(match.group(1))
            screen = self.get_screen(screen_id)
            if screen and value:
                layer_count = int(value)
                screen.layers = [Layer(id=i) for i in range(1, layer_count + 1)]
                self._notify_update()
                return f"[SCREEN] Screen {screen_id}: layers={layer_count}"
        return None
    
    def _try_parse_screen_optimized(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_SCREEN_OPTIMIZED.match(path)
        if match:
            screen_id = int(match.group(1))
            screen = self.get_screen(screen_id)
            if screen:
                screen.optimized = bool(value)
                self._notify_update()
                return f"[SCREEN] Screen {screen_id}: optimized={screen.optimized}"
        return None

    def _try_parse_screen_stereo3d(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_SCREEN_STEREO3D.match(path)
        if match:
            screen_id = int(match.group(1))
            screen = self.get_screen(screen_id)
            if screen:
                screen.is_stereo_3d = bool(value)
                self._notify_update()
                return f"[SCREEN] Screen {screen_id}: stereo3d={screen.is_stereo_3d}"
        return None

    def _try_parse_screen_region_validity(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_SCREEN_REGION_VALIDITY.match(path)
        if match:
            screen_id = int(match.group(1))
            screen = self.get_screen(screen_id)
            if screen:
                screen.region_validity = value
                self._notify_update()
                return f"[SCREEN] Screen {screen_id}: regionValidity={value}"
        return None

    def _try_parse_layer_capability(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_LAYER_CAPABILITY.match(path)
        if match:
            screen_id = int(match.group(1))
            layer_id = int(match.group(2))
            screen = self.get_screen(screen_id)
            if screen:
                layer = screen.get_layer(layer_id)
                if not layer:
                    layer = screen.add_layer(layer_id)
                layer.capability = value
                self._notify_update()
                return f"[LAYER] Screen {screen_id}, Layer {layer_id}: capability={value}"
        return None
    
    def _try_parse_layer_regions(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_LAYER_REGIONS.match(path)
        if match:
            screen_id = int(match.group(1))
            layer_id = int(match.group(2))
            screen = self.get_screen(screen_id)
            if screen:
                layer = screen.get_layer(layer_id)
                if layer:
                    layer.regions = value if value else []
                    self._notify_update()
                    return f"[LAYER] Screen {screen_id}, Layer {layer_id}: regions={value}"
        return None
    
    def _try_parse_layer_mask(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_LAYER_MASK.match(path)
        if match:
            screen_id = int(match.group(1))
            layer_id = int(match.group(2))
            screen = self.get_screen(screen_id)
            if screen:
                layer = screen.get_layer(layer_id)
                if layer:
                    layer.mask = bool(value)
                    self._notify_update()
                    return f"[LAYER] Screen {screen_id}, Layer {layer_id}: mask={layer.mask}"
        return None
    
    def _try_parse_vpu_enabled(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_VPU_ENABLED.match(path)
        if match:
            device_id = int(match.group(1))
            vpu_id = int(match.group(2))
            scaler_id = int(match.group(3))
            
            device = self.get_device(device_id)
            if device:
                vpu = device.get_vpu(vpu_id)
                if vpu:
                    scaler = vpu.get_scaler(scaler_id)
                    if scaler:
                        scaler.is_enabled = bool(value)
                        self._notify_update()
                        return f"[VPU] Device {device_id}, VPU {vpu_id}, Scaler {scaler_id}: enabled={value}"
        return None
    
    def _try_parse_vpu_available(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_VPU_AVAILABLE.match(path)
        if match:
            device_id = int(match.group(1))
            vpu_id = int(match.group(2))
            scaler_id = int(match.group(3))
            
            device = self.get_device(device_id)
            if device:
                vpu = device.get_vpu(vpu_id)
                if vpu:
                    scaler = vpu.get_scaler(scaler_id)
                    if scaler:
                        scaler.is_available = bool(value)
                        self._notify_update()
                        return f"[VPU] Device {device_id}, VPU {vpu_id}, Scaler {scaler_id}: available={value}"
        return None
    
    def _try_parse_vpu_capability(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_VPU_CAPABILITY.match(path)
        if match:
            device_id = int(match.group(1))
            vpu_id = int(match.group(2))
            scaler_id = int(match.group(3))
            
            device = self.get_device(device_id)
            if device:
                vpu = device.get_vpu(vpu_id)
                if vpu:
                    scaler = vpu.get_scaler(scaler_id)
                    if scaler:
                        scaler.capability = value
                        self._notify_update()
                        return f"[VPU] Device {device_id}, VPU {vpu_id}, Scaler {scaler_id}: capability={value}"
        return None
    
    def _try_parse_vpu_screen(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_VPU_SCREEN.match(path)
        if match:
            device_id = int(match.group(1))
            vpu_id = int(match.group(2))
            scaler_id = int(match.group(3))
            
            device = self.get_device(device_id)
            if device:
                vpu = device.get_vpu(vpu_id)
                if vpu:
                    scaler = vpu.get_scaler(scaler_id)
                    if scaler:
                        # Value is like "S1", extract number
                        if value and isinstance(value, str) and value.startswith("S"):
                            scaler.screen = int(value[1:])
                        else:
                            scaler.screen = value
                        self._notify_update()
                        return f"[VPU] Device {device_id}, VPU {vpu_id}, Scaler {scaler_id}: screen={scaler.screen}"
        return None
    
    def _try_parse_vpu_layer(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_VPU_LAYER.match(path)
        if match:
            device_id = int(match.group(1))
            vpu_id = int(match.group(2))
            scaler_id = int(match.group(3))
            
            device = self.get_device(device_id)
            if device:
                vpu = device.get_vpu(vpu_id)
                if vpu:
                    scaler = vpu.get_scaler(scaler_id)
                    if scaler:
                        # NATIVE = layer 1, otherwise value + 1
                        if value == "NATIVE":
                            scaler.layer = 1
                        else:
                            try:
                                scaler.layer = int(value) + 1
                            except (ValueError, TypeError):
                                scaler.layer = value
                        self._notify_update()
                        return f"[VPU] Device {device_id}, VPU {vpu_id}, Scaler {scaler_id}: layer={scaler.layer}"
        return None

    def _try_parse_vpu_cutnfill_capa(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_VPU_CUTNFILL_CAPA.match(path)
        if match:
            device_id = int(match.group(1))
            vpu_id = int(match.group(2))
            scaler_id = int(match.group(3))

            device = self.get_device(device_id)
            if device:
                vpu = device.get_vpu(vpu_id)
                if vpu:
                    scaler = vpu.get_scaler(scaler_id)
                    if scaler:
                        scaler.cutnfill_capa = value
                        self._notify_update()
                        return f"[VPU] Device {device_id}, VPU {vpu_id}, Scaler {scaler_id}: cutnfillCapa={value}"
        return None

    def _try_parse_vpu_seamless_capa(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_VPU_SEAMLESS_CAPA.match(path)
        if match:
            device_id = int(match.group(1))
            vpu_id = int(match.group(2))
            scaler_id = int(match.group(3))

            device = self.get_device(device_id)
            if device:
                vpu = device.get_vpu(vpu_id)
                if vpu:
                    scaler = vpu.get_scaler(scaler_id)
                    if scaler:
                        scaler.seamless_capa = value
                        self._notify_update()
                        return f"[VPU] Device {device_id}, VPU {vpu_id}, Scaler {scaler_id}: seamlessCapa={value}"
        return None

    def _try_parse_vpu_channel(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_VPU_CHANNEL.match(path)
        if match:
            device_id = int(match.group(1))
            vpu_id = int(match.group(2))
            scaler_id = int(match.group(3))

            device = self.get_device(device_id)
            if device:
                vpu = device.get_vpu(vpu_id)
                if vpu:
                    scaler = vpu.get_scaler(scaler_id)
                    if scaler:
                        scaler.channel = value
                        self._notify_update()
                        return f"[VPU] Device {device_id}, VPU {vpu_id}, Scaler {scaler_id}: channel={value}"
        return None

    def _try_parse_vpu_slice(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_VPU_SLICE.match(path)
        if match:
            device_id = int(match.group(1))
            vpu_id = int(match.group(2))
            scaler_id = int(match.group(3))

            device = self.get_device(device_id)
            if device:
                vpu = device.get_vpu(vpu_id)
                if vpu:
                    scaler = vpu.get_scaler(scaler_id)
                    if scaler:
                        scaler.slice = value
                        self._notify_update()
                        return f"[VPU] Device {device_id}, VPU {vpu_id}, Scaler {scaler_id}: slice={value}"
        return None

    def _try_parse_scaler_pipe(self, path: str, value: Any) -> Optional[str]:
        match = self.REGEX_SCALER_PIPE.match(path)
        if match:
            device_id = int(match.group(1))
            vpu_id = int(match.group(2))
            scaler_id = int(match.group(3))
            pipe_id = int(match.group(4))
            
            device = self.get_device(device_id)
            if device:
                vpu = device.get_vpu(vpu_id)
                if vpu:
                    scaler = vpu.get_scaler(scaler_id)
                    if scaler:
                        scaler.pipes[pipe_id] = value
                        self._notify_update()
                        return f"[PIPE] Device {device_id}, VPU {vpu_id}, Scaler {scaler_id}, Pipe {pipe_id}: {value}"
        return None
    
    def active_devices(self) -> List[Device]:
        """Devices that are present in the system (typed, not the debug stub)."""
        return [d for d in self.devices
                if d.device_type and d.device_type != "NLC_DBG" and d.vpu_count > 0]

    def active_screens(self) -> List[Screen]:
        return [s for s in self.screens if s.active]

    def ordered_vpu_keys(self) -> List[Tuple[int, int]]:
        """Every (device_id, vpu_id) in the system, in global order (device-major,
        vpu-minor) - e.g. device 2's VPU 3 might be the 6th entry overall. Used to
        keep a device/VPU's column position consistent everywhere it's shown."""
        return [(device.id, vpu.vpu_id)
                for device in self.active_devices()
                for vpu in device.vpus]

    def get_layer_mappings(self, screen_id: int, layer_id: int):
        """All (device, vpu, scaler) triples where an enabled mixer serves the
        given screen/layer - the join between the screen view and the VPU map."""
        results = []
        for device in self.active_devices():
            for vpu in device.vpus:
                for scaler in vpu.scalers:
                    if (scaler.is_enabled and scaler.screen == screen_id
                            and scaler.layer == layer_id):
                        results.append((device, vpu, scaler))
        return results

    def get_stats(self) -> dict:
        """Aggregate counters for the overview strip."""
        devices = self.active_devices()
        vpus = sum(d.vpu_count for d in devices)
        mixers_used = 0
        mixers_total = 0
        for device in devices:
            for vpu in device.vpus:
                mixers_total += len(vpu.scalers)
                for scaler in vpu.scalers:
                    if scaler.is_enabled:
                        mixers_used += 1
        screens = self.active_screens()
        layers = sum(len(s.layers) for s in screens)
        return {
            "devices": len(devices),
            "vpus": vpus,
            "mixers_used": mixers_used,
            "mixers_total": mixers_total,
            "screens": len(screens),
            "layers": layers,
        }

    def get_summary(self) -> str:
        """Get a summary of the current model state."""
        lines = ["=" * 60, "VPU VISUALIZER MODEL SUMMARY", "=" * 60]
        
        # Devices and VPUs
        lines.append("\n[DEVICES]")
        for device in self.devices:
            if device.device_type:
                lines.append(f"  Device {device.id}: {get_device_label(device.device_type)} ({device.vpu_count} VPUs)")
                for vpu in device.vpus:
                    active = vpu.get_active_scalers_count()
                    lines.append(f"    VPU {vpu.vpu_id}: {active}/16 scalers active ({vpu.get_usage_percentage():.0f}%)")
                    for scaler in vpu.scalers:
                        if scaler.is_enabled:
                            pipes_str = ", ".join(f"P{p}={v}" for p, v in scaler.pipes.items() if v and v != "NONE")
                            lines.append(f"      Scaler {scaler.id}: S{scaler.screen}/L{scaler.layer} cap={scaler.capability} [{pipes_str}]")
        
        # Screens
        lines.append("\n[SCREENS]")
        active_screens = [s for s in self.screens if s.active]
        for screen in active_screens:
            opt_str = " (optimized)" if screen.optimized else ""
            lines.append(f"  Screen {screen.id}: {len(screen.layers)} layers{opt_str}")
            for layer in screen.layers:
                lines.append(f"    Layer {layer.id}: cap={layer.capability} mask={layer.mask}")
        
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)
