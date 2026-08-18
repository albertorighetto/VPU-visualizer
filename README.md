# VPU Visualizer 2.0

A desktop application for visualizing VPU (Video Processing Unit) usage on Analog Way Aquilon devices, over the AWJ TCP protocol (port 10606).

See [ARCHITECTURE.md](ARCHITECTURE.md) for how Device → Proc → Mixer → Scaler → Pipe relate inside the firmware and which protocol paths the app uses.

## Features

- **VPU Map** — per-VPU mixer/pipe matrix (16 mixers × 8 out-pipe slots), color-coded by screen/layer, with capability borders and cross-VPU hover highlighting. Cards reflow with the window size; hovering a card highlights every VPU of the same device.
- **Screens & Layers** — merged view with a summary strip (devices, VPUs, mixers/pipes in use, screens, layers), searchable and filterable per-layer rows with capability icons, mask/region chips, and each layer's VPU mapping (device / VPU / mixer / pipes).
- **Pending vs Current config** — header switch between the pending configuration (API resource `new`) and the running configuration (API resource `current`).
- **Connection in the header** — host/port fields next to Connect (address persisted); the header pill shows state: disconnected / connecting / connected, active config, and live-update status (AWJ subscriptions).
- **Log** — timestamped, searchable (include/exclude text, case toggle), tag-filterable protocol log with autoscroll follow mode.

## Running from source

```bash
pip install -r requirements.txt
python main.py
```

1. Set the device IP and port in the header (defaults 127.0.0.1:10606), then hit **Connect**.
2. Pick **Pending** or **Current** in the header to choose which configuration tree to inspect. Switching re-fetches and re-subscribes.
3. The app subscribes to AWJ updates, so changes on the device appear live.

## Building executables

PyInstaller builds a standalone binary for the OS it runs on — it cannot cross-compile. Two options:

- **Local build** (current OS only):

  ```bash
  pip install pyinstaller
  pyinstaller vpu_visualizer.spec
  # result in dist/
  ```

- **All three OSes from Windows**: push a `v*` tag (or run the workflow manually from the Actions tab). `.github/workflows/build.yml` builds Windows, Linux and macOS binaries in parallel and publishes them as downloadable artifacts.

## Code map

| File | Role |
|------|------|
| `main.py` | Entry point, applies theme |
| `theme.py` | Palette, app stylesheet, chip/resource helpers |
| `main_window.py` | Header (config switch, host/port, status pill, connect), tabs |
| `awj_client.py` | AWJ TCP client; resource-aware paths (`new`/`current`), subscriptions |
| `vpu_model.py` | Data model + AWJ path parsing (resource-aware), stats, layer↔mixer join |
| `vpu_widget.py` | VPU card and pipe-cell matrix |
| `screens_panel.py` | Merged Screens + Layers + Summary view |
| `log_panel.py` | Filterable log (model/view + proxy filter) |
| `flow_layout.py` | Responsive wrapping layout for cards |

## Protocol notes

- The live AWJ TCP protocol uses `$vpuMixer` / `mixerAllocation` path segments (the device's own web UI internally calls these `$vpuLayer` / `scalerAllocation`, but the TCP API rejects those — see ARCHITECTURE.md §5).
- Pending config lives under `DeviceObject/preconfig/resources/new/…`, running config under `…/resources/current/…`.
- Messages are JSON terminated by an EOT character (`\u0004`).
