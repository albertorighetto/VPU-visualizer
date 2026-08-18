# Aquilon VPU Mapping — Internal Structure

How **Device → Proc → Mixer → Scaler → Pipe** relate inside the firmware, with
the internal item indexes and their matching enum labels. Everything below was
extracted from the device's own web UI bundle (`app.<hash>.js`, `VAR_ENUMS` +
the generated data-object reducer tree), so it reflects the *current* firmware.

---

## 1. The entities (what each thing is)

| Concept | Enum | Count | Item keys | Meaning |
|---------|------|-------|-----------|---------|
| **Device / unit** | `DEVICE` | 4 | `1,2,3,4` | Up to 4 chained chassis. Index into the mapping table. |
| **Device model** | `DEV` | 15 | `NLC_RS1`, `NLC_RS6`, `VDW_W`, … | The chassis type of each unit (drives how many Procs exist). |
| **Card / slot** | `CARD` | 21 | `MOC, IN_1..4, PROC_1..4, OUT_1..6, FRAME_1..2, FDP, FAV, AUDIO, SUPPLY` | Physical card slots. `PROC_1..4` are the VPU processor cards. |
| **Proc (VPU)** | (subset of `CARD`) | 1–4 | `PROC_1..PROC_4` | A VPU processing card. A chassis has 1–4 of them (that's the "VPU count"). |
| **Mixer / vpu-layer** | `MIXER` | 64 (16 × 4) | `PROC_1_MIXER_1 … PROC_4_MIXER_16` | The processing engines. **16 mixers per Proc.** This is the row key of the mapping table. |
| **Scaler** | `SCALER` | 2 | `A, B` | The two halves a mixer can be split into. One mixer = scaler A + scaler B. |
| **Mixing mode** | `MIXING_MODE` | 5 | `MIXER_SEAMLESS, SPLIT, MIXER_WITH_GHOST, SPLIT_INCREASED_CAPABILITY, SPLIT_WITH_GHOST` | Whether a mixer runs as one seamless engine (uses A+B together) or split into independent scalers. |
| **Out-pipe slot** | (fixed 1–8) | 8 | `usedOnOutPipe1 … usedOnOutPipe8` | Each mixer has 8 output-pipe slots (its columns in the table). |
| **Global pipe** | `PIPE` | 64 | `1 … 64` | The device's 64 physical output pipes. |
| **Pipe assignment** | `PIPE_SELECT` | 65 | `NONE, 1 … 64` | The value stored in a mixer's out-pipe slot: which global pipe it drives (or `NONE`). |

Related addressings that also appear in the bundle (not used by the mapping
table directly, listed so the names aren't mysterious):

- `PROCESSING_PIPE` (64 = 4 × 8 × 2): `PROC_x_MIXER_y_MAIN` / `_PREVIEW` — internal main/preview pipe naming per proc.
- `SCALER_MIXER` (16): `SCALER_1..8` + `MIXER_1..8` — per-proc scaler/mixer addressing.
- `SCALERWALL` (128 = 4 × 32): `PROC_x_SCALER_1..32` — scaler addressing for LED-wall mode.

---

## 2. The logic tree (containment)

```
Device (DEVICE 1..4)                         ← one chained chassis
│   model = DEV (NLC_RS1 … VDW_WMAX)
│
├── Proc / VPU card  (PROC_1 … PROC_4)        ← 1..4 depending on model
│   │
│   └── Mixer  (PROC_x_MIXER_1 … _16)         ← 16 per proc  (enum MIXER)
│       │   @props:
│       │     isAvailable   bool
│       │     isEnabled     bool
│       │     capability    LAYER_CAPABILITIES (OFF,DUAL,4K,3,5K,5,6,7,8K)
│       │     usedInScreen  SCREEN            (S1..S24)
│       │     usedInLayer   PRECONFIG_SCREEN_LAYER (NATIVE, 1..256)
│       │
│       ├── Scaler A ┐  split governed by MIXING_MODE
│       └── Scaler B ┘  (seamless = A+B as one; split = independent)
│       │
│       └── mixerAllocation                   ← the 8 out-pipe slots (protocol name; web UI calls it scalerAllocation)
│             usedOnOutPipe1 : PIPE_SELECT (NONE | 1..64)
│             usedOnOutPipe2 : PIPE_SELECT
│             …
│             usedOnOutPipe8 : PIPE_SELECT
│
└── Pipe list  (PIPE 1..64)                   ← the 64 physical output pipes
        @props: isUsed (bool)
```

**In words:** a *Device* holds up to 4 *Procs* (VPU cards). Each Proc has 16
*Mixers*. A Mixer can be split into two *Scalers* (A/B) depending on its mixing
mode, and it feeds up to 8 output-pipe slots; each slot names one of the
device's 64 global *Pipes* (or `NONE`). Screens/layers are what *consume* a
mixer — recorded on the mixer as `usedInScreen` / `usedInLayer`.

---

## 3. The table structure (how it's stored internally)

The firmware exposes this as two parallel lists per device. **Path segments
below use the names the live AWJ TCP protocol (port 10606) actually accepts —
`$vpuMixer` / `mixerAllocation` — confirmed against the device directly. The
web UI's own JS bundle names these nodes `$vpuLayer` / `scalerAllocation`
internally, but the TCP control API rejects those with error `E12`; see §5.**

```
DeviceObject/preconfig/resources/new/status/mapping/$device/@items/{1..4}/
    ├── $vpuMixer / @items / {MIXER key}      (the mixer rows)
    │        @props/isAvailable | isEnabled | capability | usedInScreen | usedInLayer
    │        mixerAllocation/@props/usedOnOutPipe1..8
    └── $pipe / @items / {1..64}              (the pipe columns)
             @props/isUsed
```

So the **allocation is literally a table**: rows = mixers, columns = the 8
out-pipe slots, cell = which global pipe that mixer drives.

```
                       out-pipe slot →
mixer ↓            P1     P2     P3     P4    P5  P6  P7  P8
PROC_1_MIXER_1    12     13     NONE   NONE  …
PROC_1_MIXER_2    NONE   NONE   NONE   NONE  …
PROC_1_MIXER_3    5      6      7      8     …
…
PROC_4_MIXER_16   …
```

A cell value of `12` means "this mixer's output slot drives global pipe 12".
`NONE` means the slot is unused. The separate `$pipe` list's `isUsed` flag is
the reverse index (which of the 64 global pipes are occupied).

---

## 4. Enum value reference (the ones this app parses)

| Property | Enum | Values |
|----------|------|--------|
| device model | `DEV` | `NLC_DBG, NLC_RS1, NLC_RS2, NLC_RS3, NLC_RS4, NLC_C, NLC_CPLUS, NLC_RSALPHA, NLC_RS5, NLC_RS6, NLC_CMAX, VDW_W, VDW_WPLUS, VDW_WMAX, NLC_CMINI` |
| screen mode | `SCREEN_MODE` | `DISABLED, FREESTYLE, STACKED`  (app treats anything ≠ `DISABLED` as active) |
| mixer/layer capability | `LAYER_CAPABILITIES` | `OFF, DUAL, 4K, 3, 5K, 5, 6, 7, 8K` |
| mixer.usedInScreen | `SCREEN` | `S1 … S24` |
| mixer.usedInLayer | `PRECONFIG_SCREEN_LAYER` | `NATIVE, 1 … 256` |
| out-pipe slot value | `PIPE_SELECT` | `NONE, 1 … 64` |
| mixing mode | `MIXING_MODE` | `MIXER_SEAMLESS, SPLIT, MIXER_WITH_GHOST, SPLIT_INCREASED_CAPABILITY, SPLIT_WITH_GHOST` |

---

## 5. ⚠ Naming note: web-UI naming ≠ wire-protocol naming

The web UI's JS bundle (`app.<hash>.js`, served on port 3000) internally names
its Redux data-object nodes **`$vpuLayer`** and **`scalerAllocation`**
(source files `vpu-layer-list.ts`, `scaler-allocation.ts`). The strings
`vpuMixer` / `mixerAllocation` do not appear anywhere in that bundle, which
made them look like stale/legacy names in our code.

**They are not.** The device's actual AWJ TCP protocol (port 10606 — what
this app and its scripts talk to) was tested directly against both forms:

- `$vpuMixer` / `mixerAllocation` → device returns real data (`capability=DUAL`, `usedInScreen=S1`, pipe usage `1/2/NONE`, etc.)
- `$vpuLayer` / `scalerAllocation` → device replies `{"error":{"code":"E12","message":"Unexpected path ..."}}`

So `$vpuMixer` / `mixerAllocation` is the **correct and only working name**
for the live control protocol. The web bundle's `$vpuLayer` /
`scalerAllocation` naming is internal to the web UI's own state layer (or a
newer node name the TCP control API doesn't expose yet) — it is not something
to port into `awj_client.py` / `vpu_model.py`. All the path-building code in
this repo (`awj_client.py`, `vpu_model.py`, `scaler_info.py`,
`enum_discovery.py`, `test_vpu_scaler.py`) correctly uses `$vpuMixer` /
`mixerAllocation` and should stay that way unless a future firmware changes
what the TCP API itself accepts (verify with `test_vpu_scaler.py` before
changing anything here again).
