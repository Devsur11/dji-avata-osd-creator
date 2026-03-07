#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DJI Avata OSD Overlay Tool — GUI Edition v2.2
Runs on Windows, macOS, and Linux

• Multi-flight detection from a single CSV
• Visual OSD layout editor with per-element toggle, X/Y offset, drag-and-drop
• Precise scale mirroring from original dji_osd_overlay.py
• Settings auto-saved to ~/.dji_osd_tool/osd_settings.json
• Overlay delay: trim first N seconds of telemetry to fix video/telemetry sync
• GPS satellite count and coordinates are separate, independently-positionable OSD elements
• GPS satellite count uses DJI-style satellite icon
"""

import cv2
import pandas as pd
import numpy as np
import os
import sys
import json
import shutil
import subprocess
import threading
import queue
import platform
from datetime import timedelta
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox


# ═════════════════════════════════════════════════════════════════════════════
#  OSD element registry (Pre-calculated normalized centers for 1920x1080)
# ═════════════════════════════════════════════════════════════════════════════
OSD_ELEMENTS = {
    "flight_mode":     dict(label="Flight Mode Box",        nx=0.023, ny=0.955, nw=0.026, nh=0.032, group="Bottom Left"),
    "vspeed_altitude": dict(label="V-Speed & Altitude",     nx=0.073, ny=0.970, nw=0.062, nh=0.028, group="Bottom Left"),
    "hspeed_distance": dict(label="H-Speed & Distance",     nx=0.135, ny=0.970, nw=0.062, nh=0.028, group="Bottom Left"),
    "horizon":         dict(label="Artificial Horizon",     nx=0.500, ny=0.500, nw=0.104, nh=0.018, group="Centre"),
    "crosshair":       dict(label="Centre Crosshair",       nx=0.500, ny=0.500, nw=0.020, nh=0.028, group="Centre"),
    "compass":         dict(label="Compass & Heading",      nx=0.510, ny=0.041, nw=0.052, nh=0.018, group="Top Centre"),
    "speed_tape":      dict(label="Speed Tape",             nx=0.031, ny=0.500, nw=0.021, nh=0.092, group="Left"),
    "pitch_roll":      dict(label="Pitch / Roll Labels",    nx=0.026, ny=0.574, nw=0.031, nh=0.046, group="Left"),
    "alt_tape":        dict(label="Altitude Tape",          nx=0.979, ny=0.500, nw=0.021, nh=0.092, group="Right"),
    "gps_sats":        dict(label="GPS Satellite Count",     nx=0.948, ny=0.012, nw=0.055, nh=0.060, group="Top Right"),
    "gps_coords":      dict(label="GPS Coordinates",         nx=0.880, ny=0.970, nw=0.040, nh=0.028, group="Bottom Right"),
    "signal":          dict(label="RC / HD Signal Bars",    nx=0.937, ny=0.962, nw=0.041, nh=0.028, group="Bottom Right"),
    "battery":         dict(label="Battery Indicator",      nx=0.969, ny=0.971, nw=0.036, nh=0.018, group="Bottom Right"),
    "rec_timer":       dict(label="Recording Timer",        nx=0.968, ny=0.026, nw=0.036, nh=0.018, group="Top Right"),
    "warnings":        dict(label="Warnings & Alerts",      nx=0.500, ny=0.624, nw=0.150, nh=0.080, group="Centre"),
    "status_icons":    dict(label="Status Icons (Sonar…)",  nx=0.500, ny=0.064, nw=0.100, nh=0.020, group="Top Centre"),
    "armed_msg":       dict(label="Armed / Disarmed Flash", nx=0.500, ny=0.648, nw=0.100, nh=0.030, group="Centre"),
    "remaining_time":  dict(label="Remaining Flight Time",  nx=0.966, ny=0.078, nw=0.050, nh=0.020, group="Top Right"),
}

# ═════════════════════════════════════════════════════════════════════════════
#  Cross-platform path helpers
# ═════════════════════════════════════════════════════════════════════════════
def get_app_data_dir() -> Path:
    """Get platform-specific application data directory for settings."""
    if platform.system() == "Windows":
        # Windows: use AppData/Local if available, fall back to home
        appdata = os.getenv("LOCALAPPDATA")
        if appdata:
            return Path(appdata) / "dji_osd_tool"
    # macOS and Linux: use ~/.dji_osd_tool
    return Path.home() / ".dji_osd_tool"


SETTINGS_DIR  = get_app_data_dir()
SETTINGS_FILE = SETTINGS_DIR / "osd_settings.json"


# ═════════════════════════════════════════════════════════════════════════════
#  Persistent OSD settings
# ═════════════════════════════════════════════════════════════════════════════
class OSDSettings:
    def __init__(self):
        self._data: dict = {}
        self.load()

    def load(self):
        try:
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE) as f:
                    self._data = json.load(f)
        except Exception:
            self._data = {}

    def save(self):
        try:
            SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            print(f"Warning: could not save settings: {e}")

    def get(self, key: str) -> dict:
        return self._data.get(key, {})

    def set_element(self, key: str, enabled: bool, dx: int, dy: int, dw: float = 0.0, dh: float = 0.0):
        self._data[key] = {"enabled": enabled, "dx": dx, "dy": dy, "dw": dw, "dh": dh}

    def is_enabled(self, key: str) -> bool:
        return self._data.get(key, {}).get("enabled", True)

    def offset(self, key: str) -> tuple:
        d = self._data.get(key, {})
        return d.get("dx", 0), d.get("dy", 0)
    
    def size(self, key: str) -> tuple:
        d = self._data.get(key, {})
        return d.get("dw", 0.0), d.get("dh", 0.0)

    def get_overlay_delay(self) -> float:
        return float(self._data.get("__overlay_delay__", 0.0))

    def set_overlay_delay(self, seconds: float):
        self._data["__overlay_delay__"] = float(seconds)

    def get_global_scale(self) -> float:
        return float(self._data.get("__global_scale__", 1.0))

    def set_global_scale(self, scale: float):
        self._data["__global_scale__"] = float(max(0.1, min(5.0, scale)))

    def get_speed_unit(self) -> str:
        return self._data.get("__speed_unit__", "m/s")

    def set_speed_unit(self, unit: str):
        self._data["__speed_unit__"] = unit if unit in ("m/s", "km/h", "mph") else "m/s"
        self.save()

    def reset_all(self):
        self._data = {}
        self.save()


# ═════════════════════════════════════════════════════════════════════════════
#  Telemetry helpers
# ═════════════════════════════════════════════════════════════════════════════
def _calc_batt_pct(row) -> int:
    """Return battery percentage (0-100) for a single telemetry row.

    Priority order:
      1. Capacity-ratio  (battery.dynamic.remain_cap_mah / full_cap_mah)
      2. Cell voltage    (battery.cells.cell_mv_list, '|'-separated mV values)
      3. flight.osd.batt_remain heuristic (legacy raw values 0-255)
    """
    # 1 — capacity ratio
    try:
        rc = float(row.get("battery.dynamic.remain_cap_mah", 0) or 0)
        fc = float(row.get("battery.dynamic.full_cap_mah",  0) or 0)
        if fc > 0 and 0 < rc <= fc * 1.05:           # small tolerance for calibration noise
            return int(max(0, min(100, rc / fc * 100)))
    except Exception:
        pass

    # 2 — cell voltages
    try:
        cl = row.get("battery.cells.cell_mv_list", None)
        if cl is not None and pd.notna(cl) and isinstance(cl, str) and "|" in cl:
            voltages = [int(x) for x in cl.split("|") if x.strip()]
            if voltages:
                v = np.mean(voltages) / 1000.0      # mean cell voltage in V
                if   v >= 4.15: p = 100
                elif v >= 4.10: p = 95 + (v - 4.10) / 0.05 * 5
                elif v >= 4.00: p = 85 + (v - 4.00) / 0.10 * 10
                elif v >= 3.90: p = 70 + (v - 3.90) / 0.10 * 15
                elif v >= 3.80: p = 50 + (v - 3.80) / 0.10 * 20
                elif v >= 3.70: p = 30 + (v - 3.70) / 0.10 * 20
                elif v >= 3.60: p = 15 + (v - 3.60) / 0.10 * 15
                elif v >= 3.50: p =  5 + (v - 3.50) / 0.10 * 10
                else:           p =  0
                return int(max(0, min(100, p)))
    except Exception:
        pass

    # 3 — flight.osd.batt_remain (raw field — can be 0-100 %, 0-200 half-%, or 200-255 mapped)
    try:
        r = float(row.get("flight.osd.batt_remain", 50) or 50)
        if r > 200: return int(80 + (r - 200) / 55 * 20)
        if r > 100: return int(r / 2)
        return int(max(0, min(100, r)))
    except Exception:
        return 50


def detect_flights(df, gap_seconds=5.0):
    rec = df[df["camera.state.record_state"] == 2].copy()
    if rec.empty:
        return []
    rec = rec.sort_values("timestamp").reset_index(drop=True)
    deltas = rec["timestamp"].diff().dt.total_seconds().fillna(0)
    rec["_seg"] = (deltas > gap_seconds).cumsum()
    flights = []
    for _, seg_df in rec.groupby("_seg"):
        seg_df = seg_df.drop(columns="_seg").reset_index(drop=True)
        start, end = seg_df["timestamp"].iloc[0], seg_df["timestamp"].iloc[-1]
        dur = (end - start).total_seconds()
        if dur < 1.0:
            continue
        try:
            vgx = seg_df.get("flight.osd.vgx_mps", pd.Series(dtype=float))
            vgy = seg_df.get("flight.osd.vgy_mps", pd.Series(dtype=float))
            speed_max = float(np.sqrt(vgx**2 + vgy**2).max())
        except Exception:
            speed_max = 0.0
        try:
            alt_max = float(seg_df.get("flight.osd.rel_h_m", pd.Series(dtype=float)).max())
        except Exception:
            alt_max = 0.0
        bs = _calc_batt_pct(seg_df.iloc[0])
        be = _calc_batt_pct(seg_df.iloc[-1])
        flights.append(dict(index=len(flights), df=seg_df, start=start, end=end,
                            duration_s=dur, samples=len(seg_df),
                            alt_max=alt_max, speed_max=speed_max,
                            batt_start=bs, batt_end=be))
    return flights


def get_video_info(path):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    fps    = cap.get(cv2.CAP_PROP_FPS)
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return dict(fps=fps, width=width, height=height,
                frames=frames, duration=frames / fps if fps > 0 else 0)


# ═════════════════════════════════════════════════════════════════════════════
#  OSD Renderer
# ═════════════════════════════════════════════════════════════════════════════
class DJIOSDOverlay:
    def __init__(self, video_path, flight_df, output_path,
                 osd_settings=None, progress_cb=None, overlay_delay=0.0):
        self.video_path  = video_path
        self.output_path = output_path
        self.progress_cb = progress_cb
        self.settings    = osd_settings if osd_settings is not None else OSDSettings()
        self.overlay_delay = float(overlay_delay)  # seconds to skip at start of telemetry

        self.recording_df = flight_df.copy()
        self.recording_df["timestamp"] = pd.to_datetime(self.recording_df["timestamp"])
        self.recording_df = self.recording_df.sort_values("timestamp").reset_index(drop=True)
        self._preprocess_battery()
        self.recording_start = self.recording_df["timestamp"].iloc[0]

        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        self.fps          = self.cap.get(cv2.CAP_PROP_FPS)
        self.width        = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height       = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fourcc   = cv2.VideoWriter_fourcc(*"mp4v")
        self.out = cv2.VideoWriter(output_path, fourcc, self.fps, (self.width, self.height))

        self.font             = cv2.FONT_HERSHEY_SIMPLEX
        self.color_white      = (255, 255, 255)
        self.color_green      = (0, 255, 0)
        self.color_red        = (0, 0, 255)
        self.color_yellow     = (0, 255, 255)
        self.color_black      = (0, 0, 0)
        self.last_armed_state = None
        self.armed_msg_frame  = 0
        self.armed_msg_dur    = 90

    def _preprocess_battery(self):
        pcts = [_calc_batt_pct(row) for _, row in self.recording_df.iterrows()]
        win = 3
        self.recording_df["battery_smooth"] = [
            int(np.mean(pcts[max(0, i - win // 2):min(len(pcts), i + win // 2 + 1)]))
            for i in range(len(pcts))
        ]

    def _tel(self, secs):
        # Apply overlay delay: shift telemetry lookup by delay seconds
        adjusted = secs + self.overlay_delay
        adjusted = max(0.0, adjusted)
        target = self.recording_start + timedelta(seconds=adjusted)
        return self.recording_df.loc[abs(self.recording_df["timestamp"] - target).idxmin()]

    def _txt(self, frame, text, pos, font_scale, color=None, thickness=1, outline=3):
        c = color if color is not None else self.color_white
        pos_int = (int(pos[0]), int(pos[1]))
        cv2.putText(frame, text, pos_int, self.font, font_scale, self.color_black, int(outline), cv2.LINE_AA)
        cv2.putText(frame, text, pos_int, self.font, font_scale, c, int(thickness), cv2.LINE_AA)

    def _get_size_scale(self, key):
        dw, dh = self.settings.size(key)
        gs = self.settings.get_global_scale()          # global multiplier (default 1.0)
        return max(0.1, (1.0 + dw) * gs), max(0.1, (1.0 + dh) * gs)

    def _en(self, key): 
        return self.settings.is_enabled(key)

    def _draw_satellite_icon(self, frame, ox, oy, es_f, sx, sy, sw, sh, sat_count):
        """Draw satellite icon rotated 45° CW + small count number.
        ox, oy = top-right corner of the whole element.
        Layout (drawn leftward from ox):  [ number ][ gap ][ icon ]
        Arc angles 130°→230° on canvas appear at lower-left after +45° rotation.
        """
        col = (255, 255, 255)

        sz  = max(18, int(22 * es_f * min(sw, sh)))
        pad = sz // 2
        csz = sz + pad * 2      # padded so rotation corners don't clip

        # ── Draw unrotated icon on temp canvas ───────────────────────────────
        canvas = np.zeros((csz, csz, 3), dtype=np.uint8)
        cx0 = pad; cy0 = pad

        # Satellite body: small rect in upper-right of icon area
        b_left  = cx0 + int(sz * 0.42)
        b_right = cx0 + int(sz * 0.95)
        b_top   = cy0 + int(sz * 0.08)
        b_bot   = cy0 + int(sz * 0.42)
        cv2.rectangle(canvas, (b_left, b_top), (b_right, b_bot), col, -1)

        # Solar panels: horizontal arms either side of body mid-height
        bmy  = (b_top + b_bot) // 2
        ph   = max(1, int(sz * 0.08))
        plen = int(sz * 0.28)
        cv2.rectangle(canvas, (b_left - plen, bmy - ph), (b_left - 1,     bmy + ph), col, -1)
        cv2.rectangle(canvas, (b_right + 1,   bmy - ph), (b_right + plen, bmy + ph), col, -1)

        # Signal arcs: center at lower-right of canvas (csz fractions),
        # opening upper-left toward body. Angles 210°→310° on canvas.
        # After -45° rotation these appear to the lower-right of the satellite.
        arc_cx    = int(csz * 0.57)
        arc_cy    = int(csz * 0.55)
        arc_thick = max(1, int(es_f * 1.5))
        r1 = max(3, int(sz * 0.28))
        r2 = max(5, int(sz * 0.55))
        for r in (r1, r2):
            cv2.ellipse(canvas, (arc_cx, arc_cy), (r, r),
                        0, 30, 130, col, arc_thick)

        # ── Rotate 45° clockwise (angle=-45 in OpenCV) ──────────────────────
        M   = cv2.getRotationMatrix2D((csz / 2, csz / 2), -45, 1.0)
        rot = cv2.warpAffine(canvas, M, (csz, csz),
                             flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))

        # ── Number: small, right-aligned to ox, at top ───────────────────────
        num_str = str(sat_count)
        font_sc = max(0.22, 0.30 * es_f)
        t_thick = max(1, int(es_f))
        (tw, th), _ = cv2.getTextSize(num_str, self.font, font_sc, t_thick)
        num_x = ox - tw
        num_y = oy + th + max(2, int(3 * es_f * sh))
        self._txt(frame, num_str, (num_x, num_y), font_sc,
                  color=col, thickness=t_thick, outline=max(1, int(2 * es_f)))

        # ── Composite icon to the left of the number ─────────────────────────
        gap    = max(3, int(5 * es_f * sw))
        icon_r = num_x - gap            # right edge of icon canvas
        dst_x1 = icon_r - csz
        dst_y1 = oy
        dst_x2 = icon_r
        dst_y2 = oy + csz

        fh, fw = frame.shape[:2]
        sx1 = max(0, -dst_x1);           sy1 = max(0, -dst_y1)
        sx2 = csz - max(0, dst_x2 - fw); sy2 = csz - max(0, dst_y2 - fh)
        dx1 = max(0, dst_x1);            dy1 = max(0, dst_y1)
        dx2 = dx1 + (sx2 - sx1);         dy2 = dy1 + (sy2 - sy1)

        if dx2 > dx1 and dy2 > dy1:
            patch  = rot[sy1:sy2, sx1:sx2]
            region = frame[dy1:dy2, dx1:dx2]
            mask   = (patch.max(axis=2) > 10).astype(np.uint8)
            kern   = np.ones((3, 3), np.uint8)
            outline_mask = cv2.dilate(mask, kern) - mask
            region[outline_mask == 1] = (0, 0, 0)
            region[mask == 1]         = col
            frame[dy1:dy2, dx1:dx2]   = region

    def draw_osd(self, frame, telemetry, video_secs):
        h, w = frame.shape[:2]
        
        # Reference scale based precisely on 1920x1080 design
        sw = w / 1920.0
        sh = h / 1080.0
        sf = min(sw, sh)
        
        # Apply GUI Editor translations (Mapping 640x360 coordinates to dynamic video bounds)
        def _get_off(key, base_x, base_y):
            odx, ody = self.settings.offset(key)
            scaled_base_x = base_x * sw
            scaled_base_y = base_y * sh
            return int(scaled_base_x + odx * (w / 640.0)), int(scaled_base_y + ody * (h / 360.0))

        # Extract telemetry
        mode_value = int(telemetry.get('flight.osd.rc_mode_channel', 0))
        flight_mode = {0: 'N', 1: 'S', 2: 'M'}.get(mode_value, 'N')
        
        vgx = telemetry.get('flight.osd.vgx_mps', 0)
        vgy = telemetry.get('flight.osd.vgy_mps', 0)
        vgz = telemetry.get('flight.osd.vgz_mps', 0)
        h_speed = np.sqrt(vgx**2 + vgy**2)
        altitude = telemetry.get('flight.osd.rel_h_m', 0)
        
        home_lat = telemetry.get('flight.home.lat_deg', 0)
        home_lon = telemetry.get('flight.home.lon_deg', 0)
        curr_lat = telemetry.get('flight.osd.lat_deg', 0)
        curr_lon = telemetry.get('flight.osd.lon_deg', 0)
        
        gps_valid = True
        if curr_lat == 0 and curr_lon == 0: gps_valid = False
        if abs(curr_lat) > 90 or abs(curr_lon) > 180: gps_valid = False
        if abs(home_lat) > 1000 or abs(home_lon) > 1000: gps_valid = False
        
        if gps_valid and home_lat != 0 and home_lon != 0:
            lat1_rad = np.radians(home_lat)
            lat2_rad = np.radians(curr_lat)
            dlat = np.radians(curr_lat - home_lat)
            dlon = np.radians(curr_lon - home_lon)
            a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
            c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
            distance_home = 6371000 * c
        else:
            distance_home = 0

        battery_pct = int(telemetry.get('battery_smooth', 50))
        gps_sats    = int(telemetry.get('flight.osd.gps_nums', 0))
        
        signal_quality = int(telemetry.get('link.signal_quality', 90))
        env_quality    = int(telemetry.get('link.env_quality', 0))
        rc_signal      = signal_quality
        hd_signal      = env_quality if env_quality > 0 else signal_quality
        
        pitch = telemetry.get('flight.osd.pitch_deg', 0)
        roll  = telemetry.get('flight.osd.roll_deg', 0)
        yaw   = telemetry.get('flight.osd.yaw_deg', 0)
        
        in_air        = telemetry.get('flight.osd.in_air', False)
        motor_on      = telemetry.get('flight.osd.motor_on', False)
        is_vibrating  = telemetry.get('flight.osd.is_vibrating', False)
        compass_err   = telemetry.get('flight.osd.compass_over_range', False)
        accel_err     = telemetry.get('flight.osd.accel_over_range', False)
        esc_stall     = telemetry.get('flight.osd.esc_stall', False)
        ultrasonic_on = telemetry.get('flight.osd.usonic_on', False)
        avoid_working = telemetry.get('flight.avoid.avoid_obstacle_working', False)
        b_gohome      = telemetry.get('flight.osd.battery_req_gohome', False)
        b_land        = telemetry.get('flight.osd.battery_req_land', False)

        # Baseline Reference Coordinations (1920x1080)
        bottom_y = 1080 - 35
        left_x   = 20
        center_x = 1920 // 2
        center_y = 1080 // 2

        # 1. Flight mode box
        if self._en("flight_mode"):
            sx, sy = self._get_size_scale("flight_mode")
            es_f = min(sx, sy) * sf
            ox, oy = _get_off("flight_mode", left_x, bottom_y - 30)
            
            mw = int(40 * sx * sw)
            mh = int(35 * sy * sh)
            slant = int(10 * sx * sw)
            pts = np.array([[ox+slant, oy], [ox+mw+slant, oy], [ox+mw, oy+mh], [ox, oy+mh]], np.int32)
            
            cv2.fillPoly(frame, [pts], self.color_white)
            cv2.polylines(frame, [pts], True, self.color_white, max(1, int(2*es_f)))
            
            tx, ty = ox + int(12 * sx * sw), oy + int(26 * sy * sh)
            cv2.putText(frame, flight_mode, (tx+1, ty+1), cv2.FONT_ITALIC, 1.0 * es_f, (50, 50, 50), max(1, int(3*es_f)), cv2.LINE_AA)
            cv2.putText(frame, flight_mode, (tx, ty), cv2.FONT_ITALIC, 1.0 * es_f, self.color_black, max(1, int(2*es_f)), cv2.LINE_AA)

        # 2. V-Speed & Altitude
        if self._en("vspeed_altitude"):
            sx, sy = self._get_size_scale("vspeed_altitude")
            es_f = min(sx, sy) * sf
            ox, oy = _get_off("vspeed_altitude", left_x + 60, bottom_y)
            _unit = self.settings.get_speed_unit()
            if _unit == "km/h":
                _vspd = vgz * 3.6
            elif _unit == "mph":
                _vspd = vgz * 2.23694
            else:
                _vspd = vgz
                _unit = "m/s"
            self._txt(frame, f"{abs(_vspd):.1f}{_unit} {'v' if vgz<0 else '^'}", (ox, oy - int(12*sy*sh)), 0.6 * es_f, thickness=max(1, int(1*es_f)), outline=max(1, int(3*es_f)))
            self._txt(frame, f"H {altitude:.1f}m", (ox, oy + int(5*sy*sh)), 0.6 * es_f, thickness=max(1, int(1*es_f)), outline=max(1, int(3*es_f)))

        # 3. H-Speed & Distance
        if self._en("hspeed_distance"):
            sx, sy = self._get_size_scale("hspeed_distance")
            es_f = min(sx, sy) * sf
            ox, oy = _get_off("hspeed_distance", left_x + 180, bottom_y)
            _unit = self.settings.get_speed_unit()
            if _unit == "km/h":
                _spd_val = h_speed * 3.6
            elif _unit == "mph":
                _spd_val = h_speed * 2.23694
            else:
                _spd_val = h_speed
                _unit = "m/s"
            self._txt(frame, f"{_spd_val:.1f}{_unit}", (ox, oy - int(12*sy*sh)), 0.6 * es_f, thickness=max(1, int(1*es_f)), outline=max(1, int(3*es_f)))
            self._txt(frame, f"D {distance_home:.0f}m", (ox, oy + int(5*sy*sh)), 0.6 * es_f, thickness=max(1, int(1*es_f)), outline=max(1, int(3*es_f)))

        # 4. Artificial Horizon
        if self._en("horizon"):
            sx, sy = self._get_size_scale("horizon")
            es_f = min(sx, sy) * sf
            ox, oy = _get_off("horizon", center_x, center_y)
            
            hw = int(100 * sx * sw)
            hoff = int(-pitch * 2.5 * sy * sh)
            rr = np.radians(roll)
            
            hx1 = int(ox - hw * np.cos(rr))
            hy1 = int(oy + hoff + hw * np.sin(rr))
            hx2 = int(ox + hw * np.cos(rr))
            hy2 = int(oy + hoff - hw * np.sin(rr))
            cv2.line(frame, (hx1, hy1), (hx2, hy2), self.color_green, max(1, int(2*es_f)))

        # 5. Crosshair
        if self._en("crosshair"):
            sx, sy = self._get_size_scale("crosshair")
            es_f = min(sx, sy) * sf
            ox, oy = _get_off("crosshair", center_x, center_y)
            
            cs_x = int(15 * sx * sw)
            cs_y = int(15 * sy * sh)
            thick = max(1, int(2*es_f))
            cv2.line(frame, (ox - cs_x, oy), (ox + cs_x, oy), self.color_white, thick)
            cv2.line(frame, (ox, oy - cs_y), (ox, oy + cs_y), self.color_white, thick)
            cv2.circle(frame, (ox, oy), max(1, int(4*es_f)), self.color_white, -1)

        # 6. Compass
        if self._en("compass"):
            sx, sy = self._get_size_scale("compass")
            es_f = min(sx, sy) * sf
            ox, oy = _get_off("compass", center_x - 30, 35)
            dirs = [(337.5,360,"N"),(0,22.5,"N"),(22.5,67.5,"NE"),(67.5,112.5,"E"),
                    (112.5,157.5,"SE"),(157.5,202.5,"S"),(202.5,247.5,"SW"),
                    (247.5,292.5,"W"),(292.5,337.5,"NW")]
            d = next((lbl for lo, hi, lbl in dirs if lo <= yaw < hi), "N")
            self._txt(frame, f"{int(yaw)} {d}", (ox, oy), 0.7 * es_f, thickness=max(1, int(1*es_f)), outline=max(1, int(3*es_f)))

        # 7. Speed Tape
        if self._en("speed_tape"):
            sx, sy = self._get_size_scale("speed_tape")
            es_f = min(sx, sy) * sf
            ox, oy = _get_off("speed_tape", 40, center_y)
            for i in range(-2, 3):
                speed_val = int(h_speed) + i * 2
                if speed_val >= 0:
                    tape_y = oy - i * int(25 * sy * sh)
                    col = self.color_white
                    sz = 0.65 if i == 0 else 0.50
                    self._txt(frame, str(speed_val), (ox, tape_y), sz * es_f, color=col, thickness=max(1, int(1*es_f)), outline=max(1, int(3*es_f)))

        # 8. Pitch/Roll Labels
        if self._en("pitch_roll"):
            sx, sy = self._get_size_scale("pitch_roll")
            es_f = min(sx, sy) * sf
            ox, oy = _get_off("pitch_roll", 20, center_y + 55)
            self._txt(frame, f"P:{pitch:.1f}", (ox, oy), 0.55 * es_f, thickness=max(1, int(1*es_f)), outline=max(1, int(3*es_f)))
            self._txt(frame, f"R:{roll:.1f}", (ox, oy + int(25 * sy * sh)), 0.55 * es_f, thickness=max(1, int(1*es_f)), outline=max(1, int(3*es_f)))

        # 9. Altitude Tape
        if self._en("alt_tape"):
            sx, sy = self._get_size_scale("alt_tape")
            es_f = min(sx, sy) * sf
            ox, oy = _get_off("alt_tape", 1920 - 60, center_y)
            for i in range(-2, 3):
                alt_val = int(altitude) + i * 5
                if alt_val >= 0:
                    tape_y = oy - i * int(25 * sy * sh)
                    col = self.color_white
                    sz = 0.65 if i == 0 else 0.50
                    self._txt(frame, str(alt_val), (ox, tape_y), sz * es_f, color=col, thickness=max(1, int(1*es_f)), outline=max(1, int(3*es_f)))

        # 10a. GPS Satellite Count — tiny DJI-style icon in top-right corner
        if self._en("gps_sats"):
            sx, sy = self._get_size_scale("gps_sats")
            es_f = min(sx, sy) * sf
            # ox,oy = TOP-LEFT of element; icon draws rightward, number follows
            ox, oy = _get_off("gps_sats", 1920 - 100, 8)
            self._draw_satellite_icon(frame, ox, oy, es_f, sx, sy, sw, sh, gps_sats)

        # 10b. GPS Coordinates
        if self._en("gps_coords"):
            sx, sy = self._get_size_scale("gps_coords")
            es_f = min(sx, sy) * sf
            ox, oy = _get_off("gps_coords", 1920 - 280, bottom_y)
            if gps_valid:
                lat_str = f"{abs(curr_lat):.6f}{'N' if curr_lat>=0 else 'S'}"
                lon_str = f"{abs(curr_lon):.6f}{'E' if curr_lon>=0 else 'W'}"
            else:
                lat_str, lon_str = "N/A", "NO GPS"
            self._txt(frame, lat_str, (ox, oy - int(10 * sy * sh)), 0.4 * es_f,
                      thickness=max(1, int(1*es_f)), outline=max(1, int(3*es_f)))
            self._txt(frame, lon_str, (ox, oy + int(6 * sy * sh)), 0.4 * es_f,
                      thickness=max(1, int(1*es_f)), outline=max(1, int(3*es_f)))

        # 11. Signal
        if self._en("signal"):
            sx, sy = self._get_size_scale("signal")
            es_f = min(sx, sy) * sf
            ox, oy = _get_off("signal", 1920 - 160, bottom_y)

            label_sc   = 0.45 * es_f
            bar_w      = int(5  * sx * sw)
            bar_gap    = int(7  * sx * sw)   # step between bar centres
            bar_pad    = int(28 * sx * sw)   # left offset from ox to first bar

            # RC row — label left, bars grow upward from baseline rc_base_y
            rc_base_y = oy - int(10 * sy * sh)
            self._txt(frame, "RC", (ox, rc_base_y),
                      label_sc, thickness=max(1, int(1*es_f)), outline=max(1, int(3*es_f)))
            rc_bars = min(4, max(1, int(rc_signal / 25 + 0.5)))
            for i in range(4):
                bar_col = self.color_white if i < rc_bars else (60, 60, 60)
                bh_i    = int((7 + i * 3) * sy * sh)
                bx      = ox + bar_pad + i * bar_gap
                cv2.rectangle(frame,
                              (bx, rc_base_y - bh_i),
                              (bx + bar_w, rc_base_y),
                              bar_col, -1)

            # HD row — same geometry, just shifted down by a fixed row spacing
            row_gap   = int(22 * sy * sh)
            hd_base_y = rc_base_y + row_gap
            self._txt(frame, "HD", (ox, hd_base_y),
                      label_sc, thickness=max(1, int(1*es_f)), outline=max(1, int(3*es_f)))
            hd_bars = min(4, max(1, int(hd_signal / 25 + 0.5)))
            for i in range(4):
                bar_col = self.color_white if i < hd_bars else (60, 60, 60)
                bh_i    = int((7 + i * 3) * sy * sh)   # identical formula as RC
                bx      = ox + bar_pad + i * bar_gap
                cv2.rectangle(frame,
                              (bx, hd_base_y - bh_i),
                              (bx + bar_w, hd_base_y),
                              bar_col, -1)

        # 12. Battery
        if self._en("battery"):
            sx, sy = self._get_size_scale("battery")
            es_f = min(sx, sy) * sf
            ox, oy = _get_off("battery", 1920 - 60, bottom_y)

            b_w   = int(40 * sx * sw)   # body width
            b_h   = int(16 * sy * sh)   # body height
            nub_w = int(4  * sx * sw)
            nub_h = int(8  * sy * sh)
            thick = max(1, int(1 * es_f))

            bx1 = ox - b_w // 2
            bx2 = bx1 + b_w
            by1 = oy - b_h // 2
            by2 = by1 + b_h

            # ── 50% opacity fill via ROI blend ───────────────────────────
            low      = battery_pct <= 20
            mid      = battery_pct <= 30
            fill_col = self.color_red if low else (self.color_yellow if mid else self.color_green)
            if battery_pct > 0:
                fx1 = bx1 + thick
                fy1 = by1 + thick
                fx2 = bx1 + thick + int((b_w - 2 * thick) * battery_pct / 100)
                fy2 = by2 - thick
                # clamp to frame bounds
                fx1c = max(0, fx1); fy1c = max(0, fy1)
                fx2c = min(w - 1, fx2); fy2c = min(h - 1, fy2)
                if fx2c > fx1c and fy2c > fy1c:
                    roi     = frame[fy1c:fy2c, fx1c:fx2c]
                    overlay = roi.copy()
                    overlay[:] = fill_col                       # BGR fill
                    frame[fy1c:fy2c, fx1c:fx2c] = \
                        cv2.addWeighted(overlay, 0.50, roi, 0.50, 0)

            # ── outline + nub drawn AFTER fill so they sit on top ────────
            cv2.rectangle(frame, (bx1, by1), (bx2, by2), self.color_white, thick)
            nub_y1 = oy - nub_h // 2
            cv2.rectangle(frame, (bx2, nub_y1), (bx2 + nub_w, nub_y1 + nub_h),
                          self.color_white, -1)

            # ── percentage text — always white, smaller than icon height ─
            pct_str = f"{battery_pct}%"
            # scale so text is ≈60% of the icon's inner height
            inner_h  = b_h - 2 * thick
            font_sc  = max(0.25, es_f * 0.38)   # deliberately small
            t_thick  = max(1, int(es_f))
            # nudge down until the rendered height fits inside the body
            (tw, th), _ = cv2.getTextSize(pct_str, self.font, font_sc, t_thick)
            tx = (bx1 + bx2) // 2 - tw // 2
            ty = (by1 + by2) // 2 + th // 2
            self._txt(frame, pct_str, (tx, ty), font_sc,
                      color=self.color_white, thickness=t_thick,
                      outline=max(1, int(1.5 * es_f)))

        # 13. Recording Timer
        if self._en("rec_timer"):
            sx, sy = self._get_size_scale("rec_timer")
            es_f = min(sx, sy) * sf
            ox, oy = _get_off("rec_timer", 1920 - 90, 30)
            
            cv2.circle(frame, (ox, oy - int(5 * sy * sh)), max(1, int(6 * es_f)), self.color_red, -1)
            m2, s2 = int(video_secs // 60), int(video_secs % 60)
            self._txt(frame, f"{m2:02d}:{s2:02d}", (ox + int(15 * sx * sw), oy), 0.7 * es_f, thickness=max(1, int(1*es_f)), outline=max(1, int(3*es_f)))

        # 14. Warnings
        if self._en("warnings"):
            sx, sy = self._get_size_scale("warnings")
            es_f = min(sx, sy) * sf
            ox, oy = _get_off("warnings", center_x, center_y + 80)
            
            warns = []
            if b_land:   warns.append(("!!! LAND NOW !!!", self.color_red, 1.0))
            elif b_gohome: warns.append(("RETURN TO HOME", self.color_red, 0.8))
            if is_vibrating: warns.append(("VIBRATION", self.color_red, 0.7))
            if compass_err: warns.append(("COMPASS ERROR", self.color_red, 0.7))
            if accel_err: warns.append(("ACCEL ERROR", self.color_red, 0.7))
            if esc_stall: warns.append(("ESC STALL", self.color_red, 0.7))
            
            for i, (text, col, sc) in enumerate(warns):
                real_sc = sc * es_f
                text_size = cv2.getTextSize(text, self.font, real_sc, max(1, int(2 * real_sc)))[0]
                text_x = ox - text_size[0] // 2
                text_y = oy + i * int(35 * sy * sh)
                self._txt(frame, text, (text_x, text_y), real_sc, color=col, thickness=max(1, int(2*real_sc)), outline=max(1, int(4*real_sc)))

        # 15. Status Icons
        if self._en("status_icons"):
            sx, sy = self._get_size_scale("status_icons")
            es_f = min(sx, sy) * sf
            ox, oy = _get_off("status_icons", center_x, 70)
            
            items = []
            if ultrasonic_on: items.append(("SONAR", self.color_green, 0.5))
            if avoid_working: items.append(("AVOID", self.color_yellow, 0.5))
            
            if items:
                tot_w = sum(len(t) * int(10 * sx * sw) for t,_,_ in items) + (len(items) - 1) * int(15 * sx * sw)
                cur_x = ox - tot_w // 2
                for text, col, sc in items:
                    self._txt(frame, text, (cur_x, oy), sc * es_f, color=col, thickness=max(1, int(1*es_f)), outline=max(1, int(3*es_f)))
                    cur_x += len(text) * int(10 * sx * sw) + int(15 * sx * sw)

        # 16. Armed / Disarmed Flash
        armed = motor_on and in_air
        show_am = False; am_text = ""
        if self.last_armed_state is not None and self.last_armed_state != armed:
            show_am = True; am_text = "ARMED" if armed else "DISARMED"
            self.armed_msg_frame = 0
        elif self.armed_msg_frame < self.armed_msg_dur:
            show_am = True; am_text = "ARMED" if self.last_armed_state else "DISARMED"
            self.armed_msg_frame += 1
        self.last_armed_state = armed

        if show_am and self._en("armed_msg"):
            sx, sy = self._get_size_scale("armed_msg")
            es_f = min(sx, sy) * sf
            ox, oy = _get_off("armed_msg", center_x, center_y + 160)
            
            sc = 1.2 * es_f
            col = self.color_white
            text_size = cv2.getTextSize(am_text, self.font, sc, max(1, int(2 * sc)))[0]
            text_x = ox - text_size[0] // 2
            self._txt(frame, am_text, (text_x, oy), sc, color=col, thickness=max(1, int(2*sc)), outline=max(1, int(4*sc)))

        # 17. Remaining Flight Time
        if self._en("remaining_time"):
            sx, sy = self._get_size_scale("remaining_time")
            es_f = min(sx, sy) * sf
            ox, oy = _get_off("remaining_time", 1920 - 90, 85)
            
            max_flight_time_s = 18 * 60 
            remaining_s = max(0, int(max_flight_time_s * battery_pct / 100.0))
            minutes = remaining_s // 60
            seconds = remaining_s % 60
            remaining_text = f"{minutes}'{seconds:02d}\""
            col = self.color_white
            self._txt(frame, remaining_text, (ox, oy), 0.7 * es_f, color=col, thickness=max(1, int(1*es_f)), outline=max(1, int(3*es_f)))

        return frame

    def process_video(self, cancel_flag=None):
        fc = 0
        while True:
            if cancel_flag and cancel_flag.is_set():
                return False
            ret, frame = self.cap.read()
            if not ret:
                break
            try:
                tel   = self._tel(fc / self.fps)
                frame = self.draw_osd(frame, tel, fc / self.fps)
            except Exception:
                pass
            self.out.write(frame)
            fc += 1
            if self.progress_cb and fc % 15 == 0:
                pct = fc / max(self.total_frames, 1) * 100
                mm, ss = int(fc/self.fps//60), int(fc/self.fps%60)
                self.progress_cb(pct, f"Processing {pct:.0f}%  —  frame {fc}/{self.total_frames}  [{mm:02d}:{ss:02d}]")
        return True

    def cleanup(self):
        self.cap.release()
        self.out.release()

    def run(self, cancel_flag=None):
        try:
            ok = self.process_video(cancel_flag)
            if self.progress_cb:
                self.progress_cb(100 if ok else 0, "Done!" if ok else "Cancelled.")
            return ok
        finally:
            self.cleanup()


# ═════════════════════════════════════════════════════════════════════════════
#  Quality reducer helpers
# ═════════════════════════════════════════════════════════════════════════════
QUALITY_PRESETS = [
    ("Ultra  (CRF 18 — archival)",   18),
    ("High   (CRF 22 — default)",    22),
    ("Medium (CRF 26 — balanced)",   26),
    ("Low    (CRF 32 — sharing)",    32),
    ("Tiny   (CRF 38 — very small)", 38),
]
RESOLUTION_PRESETS = [
    ("Original",  None, None),
    ("1080p",     1920, 1080),
    ("720p",      1280, 720),
    ("480p",      854,  480),
    ("360p",      640,  360),
]
_CRF_MBPS = {18: 18, 22: 10, 26: 5.5, 32: 2.5, 38: 0.8}
FFMPEG = shutil.which("ffmpeg")


def estimate_size_mb(duration_s, crf, w, h):
    base = _CRF_MBPS.get(crf, 5.0)
    return base * (w * h) / (1920 * 1080) * duration_s / 8


def run_ffmpeg_compress(src, dst, crf, width, height, cancel_flag, progress_cb=None):
    if not FFMPEG:
        return False, "ffmpeg not found"
    cmd = [FFMPEG, "-y", "-i", src]
    if width and height:
        cmd += ["-vf", f"scale={width}:-2"]
    cmd += ["-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
            "-movflags", "+faststart", "-c:a", "copy", dst]
    try:
        info = get_video_info(src)
        total_s = info["duration"] if info else 0
        proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True)
        for line in proc.stderr:
            if cancel_flag.is_set():
                proc.terminate(); return False, "Cancelled"
            if "time=" in line and progress_cb and total_s > 0:
                try:
                    t = line.split("time=")[1].split()[0]
                    p = t.split(":")
                    secs = float(p[0])*3600 + float(p[1])*60 + float(p[2])
                    progress_cb(secs/total_s*100, f"Compressing {secs/total_s*100:.0f}%  [{t}]")
                except Exception:
                    pass
        proc.wait()
        return (proc.returncode == 0, f"Saved to: {dst}" if proc.returncode==0
                else f"ffmpeg exited {proc.returncode}")
    except Exception as e:
        return False, str(e)


def run_opencv_compress(src, dst, crf, width, height, cancel_flag, progress_cb=None):
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        return False, "Cannot open input video"
    fps   = cap.get(cv2.CAP_PROP_FPS)
    ow    = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    oh    = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    nw, nh = (width, height) if width else (ow, oh)
    out = cv2.VideoWriter(dst, cv2.VideoWriter_fourcc(*"MJPG"), fps, (nw, nh))
    fc = 0
    while True:
        if cancel_flag.is_set():
            cap.release(); out.release(); return False, "Cancelled"
        ret, frame = cap.read()
        if not ret: break
        if (nw, nh) != (ow, oh):
            frame = cv2.resize(frame, (nw, nh))
        out.write(frame); fc += 1
        if progress_cb and fc % 30 == 0:
            pct = fc / max(total, 1) * 100
            progress_cb(pct, f"Compressing (OpenCV) {pct:.0f}%  — frame {fc}/{total}")
    cap.release(); out.release()
    return True, f"Saved to: {dst}"


# ═════════════════════════════════════════════════════════════════════════════
#  GUI palette & fonts
# ═════════════════════════════════════════════════════════════════════════════
DARK_BG   = "#1e1e2e"; PANEL_BG  = "#2a2a3e"
ACCENT    = "#89b4fa"; ACCENT2   = "#a6e3a1"
WARN_COL  = "#f38ba8"; HIGHLIGHT = "#fab387"
TEXT_FG   = "#cdd6f4"; MUTED_FG  = "#6c7086"
ENTRY_BG  = "#313244"; BTN_BG    = "#45475a"
BTN_FG    = "#cdd6f4"; SEL_BG    = "#585b70"

FN  = ("sans-serif", 10);        FNB = ("sans-serif", 10, "bold")
FNS = ("sans-serif", 9);         FNL = ("sans-serif", 13, "bold")
FNM = ("Monospace", 9)

_GROUP_COLORS = {
    "Bottom Left":  "#89b4fa",
    "Bottom Right": "#a6e3a1",
    "Centre":       "#fab387",
    "Top Centre":   "#cba6f7",
    "Top Right":    "#f38ba8",
    "Left":         "#94e2d5",
    "Right":        "#f9e2af",
}


# ═════════════════════════════════════════════════════════════════════════════
#  Tooltip
# ═════════════════════════════════════════════════════════════════════════════
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget; self.text = text; self.tw = None
        widget.bind("<Enter>", self.show); widget.bind("<Leave>", self.hide)

    def show(self, _e=None):
        x = self.widget.winfo_rootx() + 22
        y = self.widget.winfo_rooty() + 22
        self.tw = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True); tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, bg="#1e1e2e", fg="#cdd6f4",
                 relief="flat", font=FNS, padx=6, pady=4).pack()

    def hide(self, _e=None):
        if self.tw: self.tw.destroy(); self.tw = None


# ═════════════════════════════════════════════════════════════════════════════
#  FlightCard
# ═════════════════════════════════════════════════════════════════════════════
class FlightCard(tk.Frame):
    def __init__(self, parent, flight, on_select, **kw):
        super().__init__(parent, bg=PANEL_BG, cursor="hand2", **kw)
        self.flight = flight; self.on_select = on_select
        self._build()
        for w in self.winfo_children(): w.bind("<Button-1>", self._click)
        self.bind("<Button-1>", self._click)

    def _build(self):
        f = self.flight
        m, s = int(f["duration_s"]//60), int(f["duration_s"]%60)
        hdr = tk.Frame(self, bg=PANEL_BG); hdr.pack(fill="x", padx=10, pady=(8,2))
        tk.Label(hdr, text=f"Flight {f['index']+1}", bg=PANEL_BG, fg=ACCENT, font=FNB).pack(side="left")
        tk.Label(hdr, text=f"  {f['start'].strftime('%Y-%m-%d  %H:%M:%S')}",
                 bg=PANEL_BG, fg=MUTED_FG, font=FNS).pack(side="left")
        stats = tk.Frame(self, bg=PANEL_BG); stats.pack(fill="x", padx=10, pady=(0,8))
        for icon, val, tip in [
            ("dur",  f"{m:02d}:{s:02d}",              "Duration"),
            ("pts",  f"{f['samples']}",                "Telemetry samples"),
            ("alt",  f"{f['alt_max']:.0f}m",           "Max altitude"),
            ("spd",  f"{f['speed_max']:.1f}m/s",       "Max speed"),
            ("bat",  f"{f['batt_start']}->{f['batt_end']}%", "Battery"),
        ]:
            c = tk.Frame(stats, bg=PANEL_BG); c.pack(side="left", padx=(0,10))
            tk.Label(c, text=icon+":", bg=PANEL_BG, fg=MUTED_FG, font=FNS).pack(side="left")
            lbl = tk.Label(c, text=val, bg=PANEL_BG, fg=TEXT_FG, font=FNS)
            lbl.pack(side="left", padx=2); Tooltip(lbl, tip)

    def _click(self, _e=None): self.on_select(self.flight)

    def set_selected(self, v):
        bg = SEL_BG if v else PANEL_BG
        self.configure(bg=bg); self._recolor(self, bg)

    def _recolor(self, w, bg):
        try:
            if isinstance(w, tk.Frame): w.configure(bg=bg)
            for c in w.winfo_children(): self._recolor(c, bg)
        except Exception: pass


# ═════════════════════════════════════════════════════════════════════════════
#  OSD Editor Window
# ═════════════════════════════════════════════════════════════════════════════
class OSDEditorWindow(tk.Toplevel):
    def __init__(self, parent, osd_settings):
        super().__init__(parent)
        self.title("OSD Layout Editor")
        self.configure(bg=DARK_BG)
        self.geometry("1000x600")
        self.minsize(800, 450)
        self.resizable(True, True)
        self.settings  = osd_settings
        self._sel_key  = None
        self._rects    = [] 
        self._drag_key = None
        self._drag_sx  = 0; self._drag_sy  = 0
        self._drag_odx = 0; self._drag_ody = 0
        self._dx_var   = None        
        self._dy_var   = None
        self._draw_lock = False

        self.CW, self.CH = 640, 360  
        self.CX_OFFSET, self.CY_OFFSET = 0, 0 

        self._build()
        self.grab_set()

    def _build(self):
        hdr = tk.Frame(self, bg=PANEL_BG)
        hdr.pack(fill="x", pady=(0, 0))
        tk.Label(hdr, text="  OSD Layout Editor", bg=PANEL_BG, fg=ACCENT, font=FNL).pack(side="left", padx=8)
        tk.Label(hdr, text="  Drag elements to reposition. Toggle checkboxes to show/hide.",
                 bg=PANEL_BG, fg=MUTED_FG, font=FNS).pack(side="left")
        tk.Button(hdr, text="Save & Close", bg=ACCENT2, fg=DARK_BG, font=FNB,
                  relief="flat", padx=12, cursor="hand2",
                  activebackground="#79d49a", activeforeground=DARK_BG,
                  command=self._save_close).pack(side="right", padx=8, pady=6)
        tk.Button(hdr, text="Reset All", bg=BTN_BG, fg=WARN_COL, font=FNS,
                  relief="flat", padx=8, cursor="hand2",
                  activebackground=WARN_COL, activeforeground=DARK_BG,
                  command=self._reset_all).pack(side="right", padx=(0,4), pady=6)

        # ── Global Scale bar ───────────────────────────────────────────────
        scale_bar = tk.Frame(self, bg=ENTRY_BG)
        scale_bar.pack(fill="x", pady=(0, 4))
        tk.Label(scale_bar, text="  Global OSD Scale:", bg=ENTRY_BG,
                 fg=TEXT_FG, font=FNB).pack(side="left", padx=(10, 4), pady=4)
        self._global_scale_var = tk.DoubleVar(value=self.settings.get_global_scale())
        self._scale_label = tk.Label(scale_bar,
            text=f"{self.settings.get_global_scale():.2f}×",
            bg=ENTRY_BG, fg=ACCENT, font=FNB, width=6)
        self._scale_label.pack(side="left", padx=(0, 6))
        slider = tk.Scale(
            scale_bar, from_=0.25, to=3.0, resolution=0.05,
            orient="horizontal", variable=self._global_scale_var,
            bg=ENTRY_BG, fg=TEXT_FG, troughcolor=PANEL_BG,
            activebackground=ACCENT, highlightthickness=0,
            sliderlength=18, length=260, showvalue=False,
            command=self._on_global_scale)
        slider.pack(side="left", pady=2)
        for preset, label in [(0.5, "50%"), (0.75, "75%"), (1.0, "100%"),
                               (1.25, "125%"), (1.5, "150%"), (2.0, "200%")]:
            tk.Button(scale_bar, text=label,
                      bg=BTN_BG, fg=BTN_FG, relief="flat", font=FNS,
                      padx=6, pady=2, cursor="hand2",
                      activebackground=ACCENT, activeforeground=DARK_BG,
                      command=lambda v=preset: self._set_global_scale(v)
                      ).pack(side="left", padx=2, pady=4)
        tk.Frame(scale_bar, bg=ENTRY_BG).pack(side="left", expand=True)  # spacer
        # ──────────────────────────────────────────────────────────────────

        # ── Speed Unit bar ────────────────────────────────────────────────
        unit_bar = tk.Frame(self, bg=PANEL_BG)
        unit_bar.pack(fill="x", pady=(0, 4))
        tk.Label(unit_bar, text="  Speed Unit:", bg=PANEL_BG,
                 fg=TEXT_FG, font=FNB).pack(side="left", padx=(10, 8), pady=4)
        self._speed_unit_var = tk.StringVar(value=self.settings.get_speed_unit())
        for unit in ("m/s", "km/h", "mph"):
            tk.Radiobutton(
                unit_bar, text=unit, variable=self._speed_unit_var, value=unit,
                bg=PANEL_BG, fg=TEXT_FG, selectcolor=DARK_BG,
                activebackground=PANEL_BG, activeforeground=ACCENT,
                font=FN, cursor="hand2",
                command=self._on_speed_unit
            ).pack(side="left", padx=6)
        # ──────────────────────────────────────────────────────────────────

        body = tk.Frame(self, bg=DARK_BG)
        body.pack(fill="both", expand=True, padx=8, pady=8)
        pw = ttk.PanedWindow(body, orient="horizontal")
        pw.pack(fill="both", expand=True)

        cf = tk.Frame(pw, bg=PANEL_BG, highlightbackground=MUTED_FG, highlightthickness=1)
        pw.add(cf, weight=3)
        self.canvas = tk.Canvas(cf, bg="#0d0d1a", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>",       self._on_canvas_resize)
        self.canvas.bind("<ButtonPress-1>",   self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        right = tk.Frame(pw, bg=DARK_BG)
        pw.add(right, weight=1)

        tk.Label(right, text="Elements", bg=DARK_BG, fg=TEXT_FG, font=FNB).pack(anchor="w")
        sc_f = tk.Frame(right, bg=DARK_BG); sc_f.pack(fill="both", expand=True, pady=(4,0))
        sc = tk.Canvas(sc_f, bg=DARK_BG, highlightthickness=0)
        sb = ttk.Scrollbar(sc_f, orient="vertical", command=sc.yview)
        self._el_inner = tk.Frame(sc, bg=DARK_BG)
        self._el_inner.bind("<Configure>",
            lambda e, c=sc: c.configure(scrollregion=c.bbox("all")))
        sc.create_window((0,0), window=self._el_inner, anchor="nw")
        sc.configure(yscrollcommand=sb.set)
        sc.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        self._populate_list()

        sep = tk.Frame(right, bg=MUTED_FG, height=1); sep.pack(fill="x", pady=(8,6))
        self._detail_frame = tk.Frame(right, bg=DARK_BG)
        self._detail_frame.pack(fill="x")
        self._refresh_detail()

    def _populate_list(self):
        style = ttk.Style(self)
        style.configure("Elem.TCheckbutton", background=DARK_BG, foreground=TEXT_FG)
        style.map("Elem.TCheckbutton", background=[("active", DARK_BG)])

        self._elem_vars = {}
        prev_group = None
        for key, meta in OSD_ELEMENTS.items():
            if meta["group"] != prev_group:
                prev_group = meta["group"]
                col = _GROUP_COLORS.get(meta["group"], MUTED_FG)
                tk.Label(self._el_inner, text=f"  {meta['group']}", bg=DARK_BG,
                         fg=col, font=("sans-serif",8,"bold")).pack(anchor="w", padx=4, pady=(6,1))
            row = tk.Frame(self._el_inner, bg=DARK_BG, cursor="hand2")
            row.pack(fill="x", padx=4, pady=1)
            var = tk.BooleanVar(value=self.settings.is_enabled(key))
            cb  = tk.Checkbutton(row, variable=var,
                                  command=lambda k=key, v=var: self._toggle(k, v),
                                  bg=DARK_BG, activebackground=DARK_BG, selectcolor="#313244",
                                  relief="flat", bd=0)
            cb.pack(side="left")
            col = _GROUP_COLORS.get(meta["group"], TEXT_FG)
            lbl = tk.Label(row, text=meta["label"], bg=DARK_BG, fg=col, font=FNS, cursor="hand2")
            lbl.pack(side="left", padx=3)
            lbl.bind("<Button-1>", lambda e, k=key: self._select(k))
            row.bind("<Button-1>", lambda e, k=key: self._select(k))
            cb.bind("<Button-1>",  lambda e, k=key: self._select(k))
            self._elem_vars[key] = {"row": row, "var": var, "lbl": lbl}

    def _refresh_detail(self):
        for w in self._detail_frame.winfo_children(): w.destroy()
        if not self._sel_key:
            tk.Label(self._detail_frame, text="Click an element to edit its position & size",
                     bg=DARK_BG, fg=MUTED_FG, font=FNS, pady=4).pack(anchor="w")
            return

        key  = self._sel_key
        meta = OSD_ELEMENTS[key]
        dx, dy = self.settings.offset(key)
        dw, dh = self.settings.size(key)
        en     = self.settings.is_enabled(key)
        col    = _GROUP_COLORS.get(meta["group"], TEXT_FG)

        tk.Label(self._detail_frame, text=meta["label"], bg=DARK_BG,
                 fg=col, font=FNB).pack(anchor="w")
        tk.Label(self._detail_frame, text=f"Group: {meta['group']}", bg=DARK_BG,
                 fg=MUTED_FG, font=FNS).pack(anchor="w", pady=(0,6))

        en_var = tk.BooleanVar(value=en)
        def _en_cb():
            self.settings.set_element(key, en_var.get(), *self.settings.offset(key), *self.settings.size(key))
            self._elem_vars[key]["var"].set(en_var.get())
            self._draw_preview()
        tk.Checkbutton(self._detail_frame, text="  Enabled", variable=en_var,
                       command=_en_cb, bg=DARK_BG, fg=TEXT_FG,
                       activebackground=DARK_BG, selectcolor="#313244",
                       relief="flat", font=FNS).pack(anchor="w")

        self._dx_var = tk.IntVar(value=dx)
        self._dy_var = tk.IntVar(value=dy)
        self._dw_var = tk.DoubleVar(value=dw)
        self._dh_var = tk.DoubleVar(value=dh)

        def _offset_changed(*_):
            if self._draw_lock: return
            try:
                ndx = self._dx_var.get(); ndy = self._dy_var.get()
                ndw = self._dw_var.get(); ndh = self._dh_var.get()
                self.settings.set_element(key, self.settings.is_enabled(key), ndx, ndy, ndw, ndh)
                self._draw_preview()
            except Exception: pass

        for label, var, from_, to in [("X offset (px)", self._dx_var, -1000, 1000),
                                       ("Y offset (px)", self._dy_var, -1000, 1000),
                                       ("Width scale", self._dw_var, -1.0, 1.0),
                                       ("Height scale", self._dh_var, -1.0, 1.0)]:
            row = tk.Frame(self._detail_frame, bg=DARK_BG); row.pack(fill="x", pady=2)
            tk.Label(row, text=label, bg=DARK_BG, fg=TEXT_FG, font=FNS,
                     width=14, anchor="w").pack(side="left")
            sp = tk.Spinbox(row, from_=from_, to=to, textvariable=var, width=7,
                            bg=ENTRY_BG, fg=TEXT_FG, relief="flat",
                            buttonbackground=BTN_BG, insertbackground=TEXT_FG, font=FNS,
                            command=_offset_changed, increment=0.05 if var in (self._dw_var, self._dh_var) else 1)
            sp.pack(side="left", padx=4)
            var.trace_add("write", _offset_changed)

        def _reset_elem():
            self.settings.set_element(key, True, 0, 0, 0.0, 0.0)
            self._elem_vars[key]["var"].set(True)
            self._refresh_detail(); self._draw_preview()
        tk.Button(self._detail_frame, text="Reset this element",
                  bg=BTN_BG, fg=BTN_FG, relief="flat", font=FNS, cursor="hand2",
                  activebackground=MUTED_FG, command=_reset_elem).pack(anchor="w", pady=(8,0))

    def _on_canvas_resize(self, event):
        w, h = event.width, event.height
        if w < 10 or h < 10: return
        if w / h > 16/9:
            self.CH = h
            self.CW = int(h * 16/9)
        else:
            self.CW = w
            self.CH = int(w * 9/16)
        self.CX_OFFSET = (w - self.CW) // 2
        self.CY_OFFSET = (h - self.CH) // 2
        self._draw_preview()

    def _draw_preview(self):
        self.canvas.delete("all")
        self._rects = []
        cw, ch = self.CW, self.CH
        cx0, cy0 = self.CX_OFFSET, self.CY_OFFSET

        self.canvas.create_rectangle(cx0, cy0, cx0+cw, cy0+ch, fill="#0d0d1a", outline="#313244", width=2)
        for gx in range(0, cw, max(1, cw//12)):
            self.canvas.create_line(cx0+gx, cy0, cx0+gx, cy0+ch, fill="#181828")
        for gy in range(0, ch, max(1, ch//9)):
            self.canvas.create_line(cx0, cy0+gy, cx0+cw, cy0+gy, fill="#181828")
        self.canvas.create_line(cx0, cy0+ch//2, cx0+cw, cy0+ch//2, fill="#1c1c30", dash=(4,4))
        self.canvas.create_line(cx0+cw//2, cy0, cx0+cw//2, cy0+ch, fill="#1c1c30", dash=(4,4))

        for key, meta in OSD_ELEMENTS.items():
            dx, dy  = self.settings.offset(key)
            dw, dh  = self.settings.size(key)
            enabled = self.settings.is_enabled(key)
            is_sel  = key == self._sel_key
            gs      = self.settings.get_global_scale()
            
            dx_canvas = dx * (cw / 640.0)
            dy_canvas = dy * (ch / 360.0)
            
            ecx = cx0 + meta["nx"] * cw + dx_canvas
            ecy = cy0 + meta["ny"] * ch + dy_canvas
            ew  = meta["nw"] * cw * max(0.1, (1.0 + dw) * gs)
            eh  = meta["nh"] * ch * max(0.1, (1.0 + dh) * gs)
            
            x0 = int(ecx - ew/2); y0 = int(ecy - eh/2)
            x1 = int(ecx + ew/2); y1 = int(ecy + eh/2)

            col  = _GROUP_COLORS.get(meta["group"], "#888")
            dash = () if enabled else (3,3)
            fg   = col if enabled else "#3a3a5a"
            fill = col if is_sel and enabled else ""
            lw   = 2 if is_sel else 1

            self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=fg, width=lw, dash=dash)

            self.canvas.create_text(
                (x0+x1)//2, (y0+y1)//2,
                text=meta["label"], fill="black" if is_sel and enabled else fg,
                font=("sans-serif", 6, "bold" if is_sel else "normal"), width=max(1, x1-x0-2), anchor="center")

            if is_sel and enabled:
                hx, hy = (x0+x1)//2, (y0+y1)//2
                self.canvas.create_oval(hx-4, hy-4, hx+4, hy+4, fill=col, outline="white", width=1)

            self._rects.append((key, x0, y0, x1, y1))

        self.canvas.create_text(cx0+4, cy0+4, text="drag to move  |  list to toggle",
                                fill=MUTED_FG, font=("sans-serif",7), anchor="nw")

    def _select(self, key):
        self._sel_key = key
        for k, row in self._elem_vars.items():
            bg = SEL_BG if k==key else DARK_BG
            row["row"].configure(bg=bg)
            try: row["lbl"].configure(bg=bg)
            except: pass
        self._refresh_detail()
        self._draw_preview()

    def _toggle(self, key, var):
        dx, dy = self.settings.offset(key)
        dw, dh = self.settings.size(key)
        self.settings.set_element(key, var.get(), dx, dy, dw, dh)
        self._draw_preview()

    def _on_press(self, event):
        self._drag_key = None
        for key, x0, y0, x1, y1 in reversed(self._rects):
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                self._drag_key = key
                self._drag_sx  = event.x; self._drag_sy = event.y
                dx, dy = self.settings.offset(key)
                self._drag_odx = dx; self._drag_ody = dy
                self._select(key); break

    def _on_drag(self, event):
        if not self._drag_key: return
        sc_x = 640.0 / self.CW
        sc_y = 360.0 / self.CH
        ndx = int(self._drag_odx + (event.x - self._drag_sx) * sc_x)
        ndy = int(self._drag_ody + (event.y - self._drag_sy) * sc_y)
        
        dw, dh = self.settings.size(self._drag_key)
        self.settings.set_element(self._drag_key, self.settings.is_enabled(self._drag_key), ndx, ndy, dw, dh)
        
        self._draw_lock = True
        if self._dx_var and self._dy_var:
            self._dx_var.set(ndx); self._dy_var.set(ndy)
        self._draw_lock = False
        self._draw_preview()

    def _on_release(self, _event):
        self._drag_key = None

    def _reset_all(self):
        if messagebox.askyesno("Reset All", "Reset all OSD elements to default positions and enable all?", parent=self):
            self.settings.reset_all()
            for key, row in self._elem_vars.items():
                row["var"].set(True)
            self._sel_key = None
            self._refresh_detail(); self._draw_preview()

    def _on_speed_unit(self):
        self.settings.set_speed_unit(self._speed_unit_var.get())

    def _on_global_scale(self, _val=None):
        try:
            gs = float(self._global_scale_var.get())
        except (ValueError, tk.TclError):
            gs = 1.0
        gs = max(0.25, min(3.0, gs))
        self._global_scale_var.set(round(gs, 2))
        self._scale_label.configure(text=f"{gs:.2f}×")
        self.settings.set_global_scale(gs)
        self._draw_preview()

    def _set_global_scale(self, value: float):
        self._global_scale_var.set(value)
        self._on_global_scale()

    def _save_close(self):
        self.settings.save(); self.destroy()


# ═════════════════════════════════════════════════════════════════════════════
#  Main Application
# ═════════════════════════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DJI Avata OSD Overlay Tool")
        self.configure(bg=DARK_BG)
        self.geometry("1240x780")
        self.minsize(900, 600)

        self.osd_settings    = OSDSettings()
        self.csv_path        = ""
        self.flights         = []
        self.selected_flight = None
        self.flight_cards    = []
        self._proc_queue     = queue.Queue()
        self._processing     = False
        self._q_proc         = False
        self._q_cancel       = threading.Event()

        self._apply_style()
        self._build_ui()
        self._poll_queue()

    def _apply_style(self):
        s = ttk.Style(self); s.theme_use("clam")
        s.configure("TProgressbar", troughcolor=PANEL_BG, background=ACCENT,
                    bordercolor=PANEL_BG, lightcolor=ACCENT, darkcolor=ACCENT)
        s.configure("Vertical.TScrollbar", background=BTN_BG,
                    troughcolor=PANEL_BG, bordercolor=PANEL_BG, arrowcolor=TEXT_FG)
        s.configure("TNotebook",     background=DARK_BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=BTN_BG, foreground=TEXT_FG,
                    padding=(16,7), font=FNB)
        s.map("TNotebook.Tab",
              background=[("selected", PANEL_BG)],
              foreground=[("selected", ACCENT)])

    def _build_ui(self):
        topbar = tk.Frame(self, bg=PANEL_BG)
        topbar.pack(fill="x")
        tk.Label(topbar, text="  DJI Avata OSD Overlay", bg=PANEL_BG,
                 fg=ACCENT, font=FNL).pack(side="left", padx=10, pady=10)
        tk.Button(topbar, text="  Open Telemetry CSV",
                  bg=BTN_BG, fg=BTN_FG, font=FNB, relief="flat",
                  padx=12, pady=6, cursor="hand2",
                  activebackground=ACCENT, activeforeground=DARK_BG,
                  command=self._load_csv).pack(side="left", padx=10, pady=8)
        self.csv_label = tk.Label(topbar, text="No file loaded",
                                  bg=PANEL_BG, fg=MUTED_FG, font=FNS)
        self.csv_label.pack(side="left")
        
        sett_path = str(SETTINGS_FILE)
        self.sett_btn = tk.Button(topbar,
            text="  OSD Editor",
            bg=BTN_BG, fg=HIGHLIGHT, font=FNB, relief="flat",
            padx=12, pady=6, cursor="hand2",
            activebackground=HIGHLIGHT, activeforeground=DARK_BG,
            command=self._open_osd_editor)
        self.sett_btn.pack(side="right", padx=12, pady=8)
        Tooltip(self.sett_btn, f"Edit overlay layout\nSettings saved to:\n{sett_path}")

        main = tk.Frame(self, bg=DARK_BG)
        main.pack(fill="both", expand=True)

        pw = ttk.PanedWindow(main, orient="horizontal")
        pw.pack(fill="both", expand=True, padx=8, pady=8)

        left = tk.Frame(pw, bg=DARK_BG, width=380)
        pw.add(left, weight=1)
        tk.Label(left, text="Detected Flights", bg=DARK_BG,
                 fg=TEXT_FG, font=FNB).pack(anchor="w", pady=(0,4))
        scf = tk.Frame(left, bg=DARK_BG); scf.pack(fill="both", expand=True)
        sc  = tk.Canvas(scf, bg=DARK_BG, highlightthickness=0)
        sb  = ttk.Scrollbar(scf, orient="vertical", command=sc.yview,
                            style="Vertical.TScrollbar")
        self.flights_inner = tk.Frame(sc, bg=DARK_BG)
        self.flights_inner.bind("<Configure>",
            lambda e, c=sc: c.configure(scrollregion=c.bbox("all")))
        sc.create_window((0,0), window=self.flights_inner, anchor="nw")
        sc.configure(yscrollcommand=sb.set)
        sc.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        self._no_fl = tk.Label(self.flights_inner,
                               text="Load a CSV file\nto detect flights.",
                               bg=DARK_BG, fg=MUTED_FG, font=FN, justify="center")
        self._no_fl.pack(pady=30)

        right = tk.Frame(pw, bg=DARK_BG)
        pw.add(right, weight=3)
        nb = ttk.Notebook(right); nb.pack(fill="both", expand=True)
        tab_ov   = tk.Frame(nb, bg=DARK_BG); nb.add(tab_ov,   text="   Overlay   ")
        tab_q    = tk.Frame(nb, bg=DARK_BG); nb.add(tab_q,    text="   Quality Reducer   ")
        tab_help = tk.Frame(nb, bg=DARK_BG); nb.add(tab_help, text="   Help   ")
        tab_about= tk.Frame(nb, bg=DARK_BG); nb.add(tab_about,text="   About   ")
        self._build_overlay_tab(tab_ov)
        self._build_quality_tab(tab_q)
        self._build_help_tab(tab_help)
        self._build_about_tab(tab_about)

    def _build_overlay_tab(self, p):
        self.detail_frame = tk.Frame(p, bg=PANEL_BG)
        self.detail_frame.pack(fill="x", pady=(0,6))
        tk.Label(self.detail_frame, text="Select a flight from the list",
                 bg=PANEL_BG, fg=MUTED_FG, font=FN, pady=12).pack()

        vf = tk.Frame(p, bg=DARK_BG); vf.pack(fill="x", pady=(0,3))
        tk.Label(vf, text="Video File", bg=DARK_BG, fg=TEXT_FG, font=FNB).pack(anchor="w")
        vr = tk.Frame(vf, bg=DARK_BG); vr.pack(fill="x", pady=2)
        self.vid_entry = tk.Entry(vr, bg=ENTRY_BG, fg=TEXT_FG, relief="flat",
                                  font=FN, insertbackground=TEXT_FG)
        self.vid_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0,6))
        tk.Button(vr, text="Browse", bg=BTN_BG, fg=BTN_FG, relief="flat",
                  padx=10, cursor="hand2",
                  activebackground=ACCENT, activeforeground=DARK_BG,
                  command=self._browse_video).pack(side="left")

        self.sync_frame = tk.Frame(p, bg=PANEL_BG); self.sync_frame.pack(fill="x", pady=(0,3))
        tk.Label(self.sync_frame, text="Sync Verification", bg=PANEL_BG,
                 fg=ACCENT, font=FNB, pady=3).pack(anchor="w", padx=10)
        self.sync_result = tk.Label(self.sync_frame,
            text="Load a CSV and select a flight, then pick a video.",
            bg=PANEL_BG, fg=MUTED_FG, font=FNS, wraplength=680, justify="left", pady=2)
        self.sync_result.pack(anchor="w", padx=10, pady=(0,5))

        # ── Overlay Delay ──────────────────────────────────────────────────
        delay_frame = tk.Frame(p, bg=PANEL_BG); delay_frame.pack(fill="x", pady=(0,3))
        tk.Label(delay_frame, text="Overlay Delay", bg=PANEL_BG,
                 fg=ACCENT, font=FNB, pady=3).pack(anchor="w", padx=10)
        delay_inner = tk.Frame(delay_frame, bg=PANEL_BG); delay_inner.pack(fill="x", padx=10, pady=(0,6))
        self._delay_var = tk.DoubleVar(value=self.osd_settings.get_overlay_delay())
        delay_spin = tk.Spinbox(
            delay_inner, from_=-120.0, to=120.0, increment=0.1,
            textvariable=self._delay_var, width=8,
            bg=ENTRY_BG, fg=TEXT_FG, relief="flat", font=FN,
            insertbackground=TEXT_FG, buttonbackground=BTN_BG,
            command=self._save_delay)
        delay_spin.pack(side="left")
        delay_spin.bind("<FocusOut>", lambda e: self._save_delay())
        delay_spin.bind("<Return>",   lambda e: self._save_delay())
        tk.Label(delay_inner, text=" seconds  (positive = skip start of telemetry, negative = skip start of video)",
                 bg=PANEL_BG, fg=MUTED_FG, font=FNS).pack(side="left", padx=6)
        # ──────────────────────────────────────────────────────────────────

        of = tk.Frame(p, bg=DARK_BG); of.pack(fill="x", pady=(0,3))
        tk.Label(of, text="Output File", bg=DARK_BG, fg=TEXT_FG, font=FNB).pack(anchor="w")
        or2 = tk.Frame(of, bg=DARK_BG); or2.pack(fill="x", pady=2)
        self.out_entry = tk.Entry(or2, bg=ENTRY_BG, fg=TEXT_FG, relief="flat",
                                  font=FN, insertbackground=TEXT_FG)
        self.out_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0,6))
        tk.Button(or2, text="Save as", bg=BTN_BG, fg=BTN_FG, relief="flat",
                  padx=10, cursor="hand2",
                  activebackground=ACCENT, activeforeground=DARK_BG,
                  command=self._browse_output).pack(side="left")

        br = tk.Frame(p, bg=DARK_BG); br.pack(fill="x", pady=(6,0))
        self.process_btn = tk.Button(br, text="Generate OSD Overlay",
            bg=ACCENT2, fg=DARK_BG, font=FNB, relief="flat", padx=18, pady=10,
            cursor="hand2", activebackground="#79d49a", activeforeground=DARK_BG,
            command=self._start_processing, state="disabled")
        self.process_btn.pack(side="left")
        self.cancel_btn = tk.Button(br, text="Cancel",
            bg=WARN_COL, fg=DARK_BG, font=FNB, relief="flat", padx=14, pady=10,
            cursor="hand2", activebackground="#e0637a", activeforeground=DARK_BG,
            command=self._cancel_processing, state="disabled")
        self.cancel_btn.pack(side="left", padx=(8,0))

        pf = tk.Frame(p, bg=DARK_BG); pf.pack(fill="x", pady=(4,0))
        self.progress_var = tk.DoubleVar()
        ttk.Progressbar(pf, variable=self.progress_var, maximum=100).pack(fill="x")
        self.progress_label = tk.Label(pf, text="", bg=DARK_BG, fg=MUTED_FG, font=FNS)
        self.progress_label.pack(anchor="w", pady=2)

        tk.Label(p, text="Log", bg=DARK_BG, fg=TEXT_FG, font=FNB).pack(anchor="w", pady=(4,2))
        lf = tk.Frame(p, bg=PANEL_BG); lf.pack(fill="both", expand=True)
        self.log_text = tk.Text(lf, bg=PANEL_BG, fg=TEXT_FG, relief="flat",
                                font=FNM, state="disabled", wrap="word",
                                insertbackground=TEXT_FG, selectbackground=SEL_BG)
        ls = ttk.Scrollbar(lf, command=self.log_text.yview, style="Vertical.TScrollbar")
        self.log_text.configure(yscrollcommand=ls.set)
        self.log_text.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        ls.pack(side="right", fill="y")
        for tag, col in [("ok",ACCENT2),("warn",HIGHLIGHT),("err",WARN_COL),("info",ACCENT)]:
            self.log_text.tag_configure(tag, foreground=col)

    def _build_quality_tab(self, p):
        self._q_queue = queue.Queue()

        ff_ok  = FFMPEG is not None
        banner = tk.Frame(p, bg=PANEL_BG); banner.pack(fill="x", pady=(0,8))
        if ff_ok:
            tk.Label(banner, text=f"  ffmpeg found: {FFMPEG}",
                     bg=PANEL_BG, fg=ACCENT2, font=FNS, pady=6).pack(anchor="w", padx=10)
        else:
            tk.Label(banner, text="  ffmpeg not found — using OpenCV fallback (limited quality control)",
                     bg=PANEL_BG, fg=HIGHLIGHT, font=FNS, pady=4).pack(anchor="w", padx=10)
            tk.Label(banner, text="  Install ffmpeg for best results:  sudo apt install ffmpeg",
                     bg=PANEL_BG, fg=MUTED_FG, font=FNS).pack(anchor="w", padx=10, pady=(0,4))

        irow = tk.Frame(p, bg=DARK_BG); irow.pack(fill="x", pady=(0,4))
        tk.Label(irow, text="Input Video", bg=DARK_BG, fg=TEXT_FG, font=FNB).pack(anchor="w")
        ir2 = tk.Frame(irow, bg=DARK_BG); ir2.pack(fill="x", pady=2)
        self.q_in_entry = tk.Entry(ir2, bg=ENTRY_BG, fg=TEXT_FG, relief="flat",
                                   font=FN, insertbackground=TEXT_FG)
        self.q_in_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0,6))
        tk.Button(ir2, text="Browse", bg=BTN_BG, fg=BTN_FG, relief="flat",
                  padx=10, cursor="hand2",
                  activebackground=ACCENT, activeforeground=DARK_BG,
                  command=self._q_browse_input).pack(side="left")

        sr = tk.Frame(p, bg=DARK_BG); sr.pack(fill="x", pady=(4,0))

        rs = tk.Frame(sr, bg=DARK_BG); rs.pack(side="left", padx=(0,20))
        tk.Label(rs, text="Resolution", bg=DARK_BG, fg=TEXT_FG, font=FNB).pack(anchor="w")
        self.q_res_var = tk.StringVar(value=RESOLUTION_PRESETS[0][0])
        res_box = ttk.Combobox(rs, textvariable=self.q_res_var, state="readonly",
                               width=12, values=[r[0] for r in RESOLUTION_PRESETS])
        res_box.pack(pady=4)
        res_box.bind("<<ComboboxSelected>>", lambda e: self._q_update_estimate())

        qs = tk.Frame(sr, bg=DARK_BG); qs.pack(side="left", padx=(0,20))
        tk.Label(qs, text="Quality", bg=DARK_BG, fg=TEXT_FG, font=FNB).pack(anchor="w")
        self.q_qual_var = tk.StringVar(value=QUALITY_PRESETS[1][0])
        qual_box = ttk.Combobox(qs, textvariable=self.q_qual_var, state="readonly",
                                width=28, values=[q[0] for q in QUALITY_PRESETS])
        qual_box.pack(pady=4)
        qual_box.bind("<<ComboboxSelected>>", lambda e: self._q_update_estimate())

        self.q_estimate = tk.Label(sr, text="", bg=DARK_BG, fg=MUTED_FG, font=FNS, justify="left")
        self.q_estimate.pack(side="left")

        of = tk.Frame(p, bg=DARK_BG); of.pack(fill="x", pady=(8,4))
        tk.Label(of, text="Output File", bg=DARK_BG, fg=TEXT_FG, font=FNB).pack(anchor="w")
        or2 = tk.Frame(of, bg=DARK_BG); or2.pack(fill="x", pady=2)
        self.q_out_entry = tk.Entry(or2, bg=ENTRY_BG, fg=TEXT_FG, relief="flat",
                                    font=FN, insertbackground=TEXT_FG)
        self.q_out_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0,6))
        tk.Button(or2, text="Save as", bg=BTN_BG, fg=BTN_FG, relief="flat",
                  padx=10, cursor="hand2",
                  activebackground=ACCENT, activeforeground=DARK_BG,
                  command=self._q_browse_output).pack(side="left")

        qbr = tk.Frame(p, bg=DARK_BG); qbr.pack(fill="x", pady=(8,0))
        self.q_run_btn = tk.Button(qbr, text="Compress / Re-encode",
            bg=ACCENT2, fg=DARK_BG, font=FNB, relief="flat", padx=18, pady=10,
            cursor="hand2", activebackground="#79d49a", activeforeground=DARK_BG,
            command=self._q_start)
        self.q_run_btn.pack(side="left")
        self.q_cancel_btn = tk.Button(qbr, text="Cancel",
            bg=WARN_COL, fg=DARK_BG, font=FNB, relief="flat", padx=14, pady=10,
            cursor="hand2", state="disabled",
            activebackground="#e0637a", activeforeground=DARK_BG,
            command=self._q_cancel)
        self.q_cancel_btn.pack(side="left", padx=(8,0))

        qpf = tk.Frame(p, bg=DARK_BG); qpf.pack(fill="x", pady=(5,0))
        self.q_prog_var = tk.DoubleVar()
        ttk.Progressbar(qpf, variable=self.q_prog_var, maximum=100).pack(fill="x")
        self.q_prog_lbl = tk.Label(qpf, text="", bg=DARK_BG, fg=MUTED_FG, font=FNS)
        self.q_prog_lbl.pack(anchor="w", pady=2)

        info = tk.Label(p, justify="left", anchor="w", padx=14, pady=10,
                        bg=PANEL_BG, fg=MUTED_FG, font=FNS,
                        text=(
                            "Quality guide (H.264 CRF scale — lower = better):\n"
                            "  Ultra  CRF 18 — visually lossless, ~15–20 Mbps at 1080p\n"
                            "  High   CRF 22 — excellent quality, ~8–12 Mbps\n"
                            "  Medium CRF 26 — good balance, ~4–6 Mbps\n"
                            "  Low    CRF 32 — smaller file, slight loss, ~2–3 Mbps\n"
                            "  Tiny   CRF 38 — heavily compressed, ~0.5–1 Mbps\n\n"
                            "Recommended for social sharing: Low or Medium at 720p."
                        ))
        info.pack(fill="x", pady=(8,0))

    def _build_help_tab(self, p):
        """Build the Help tab with usage instructions."""
        sc = tk.Canvas(p, bg=DARK_BG, highlightthickness=0)
        sb = ttk.Scrollbar(p, orient="vertical", command=sc.yview,
                           style="Vertical.TScrollbar")
        inner = tk.Frame(sc, bg=DARK_BG)
        inner.bind("<Configure>", lambda e, c=sc: c.configure(scrollregion=c.bbox("all")))
        sc.create_window((0, 0), window=inner, anchor="nw")
        sc.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); sc.pack(fill="both", expand=True)
        sc.bind("<MouseWheel>", lambda e, c=sc: c.yview_scroll(int(-1*(e.delta/120)), "units"))

        def _section(title, body):
            tk.Label(inner, text=title, bg=DARK_BG, fg=ACCENT, font=FNB,
                     anchor="w", padx=20).pack(fill="x", pady=(8, 0))
            tk.Frame(inner, bg=ACCENT, height=1).pack(fill="x", padx=20, pady=(2, 4))
            tk.Label(inner, text=body, bg=DARK_BG, fg=TEXT_FG, font=FNS,
                     anchor="w", justify="left", padx=32,
                     wraplength=680).pack(fill="x", pady=(0, 2))

        tk.Label(inner, text="How to Use — DJI Avata OSD Overlay Tool",
                 bg=DARK_BG, fg=ACCENT2, font=FNL, padx=20, pady=12).pack(fill="x")

        _section("Step 1 — Load Your Telemetry CSV",
            "Click  Open Telemetry CSV  in the top bar and select the CSV file exported "
            "from SquirellCast FPV android app (Other sources may work but are not tested). The tool will "
            "automatically detect individual recording sessions from the "
            "camera.state.record_state column and list them as Flight 1, Flight 2, etc.")

        _section("Step 2 — Select a Flight",
            "Click a flight card on the left panel to select it. Flight statistics "
            "(duration, max altitude, max speed, battery usage) are shown in the detail "
            "panel at the top right. The tool selects Flight 1 automatically.")

        _section("Step 3 — Pick a Video File",
            "Under the Overlay tab, click Browse next to Video File and choose the "
            "corresponding DJI video clip. The Sync Verification section will compare the "
            "telemetry duration against the video duration and give a green/yellow/red "
            "status. A mismatch under 2 s is fine. A large mismatch usually means the "
            "wrong clip is selected.")

        _section("Step 4 — Overlay Delay (optional sync fix)",
            "If the OSD appears to lag behind or run ahead of the action, use the "
            "Overlay Delay spinner to compensate:\n\n"
            "  Positive value (+N s)  — telemetry is shifted forward in time. "
            "Use this when the telemetry appears too early (OSD shows landing before "
            "the video does).\n\n"
            "  Negative value (−N s)  — telemetry is shifted backward. "
            "Use this when the OSD lags behind the video.\n\n"
            "The delay accepts decimal fractions (e.g. 1.5, −0.3). "
            "The value is saved automatically.")

        _section("Step 5 — OSD Layout Editor",
            "Click  OSD Editor  in the top-right corner to open the visual layout editor. "
            "You can:\n"
            "  • Drag each element to any position on the 640×360 canvas\n"
            "  • Toggle checkboxes to show or hide individual elements\n"
            "  • Select an element and adjust its X/Y offset or size in the detail panel\n"
            "  • Click Reset All to restore defaults\n\n"
            "All positions are saved to  ~/.dji_osd_tool/osd_settings.json  and "
            "persist between sessions.")

        _section("Step 6 — GPS Elements",
            "GPS Satellite Count and GPS Coordinates are now independent OSD elements. "
            "You can position them separately in the OSD Editor.\n\n"
            "  GPS Satellite Count  shows a DJI-style satellite icon followed by the "
            "number of locked satellites.\n\n"
            "  GPS Coordinates  shows the current latitude and longitude of the drone.")

        _section("Step 7 — Generate the Overlay",
            "Set the output file path (auto-suggested next to the CSV), then click "
            "Generate OSD Overlay. Progress is shown in the progress bar and log below. "
            "Click Cancel at any time to abort. The output is an MP4 file with the OSD "
            "burned into every frame.\n\n"
            "Note: the output uses the mp4v codec. For social sharing, run it through the "
            "Quality Reducer tab afterwards to re-encode with H.264.")

        _section("Quality Reducer Tab",
            "Re-encode any video to a smaller H.264 MP4. Select resolution and quality "
            "preset, pick input/output files, and click Compress / Re-encode. "
            "If ffmpeg is installed, it will be used for best quality. "
            "Otherwise, an OpenCV fallback is used.")

        _section("Tips & Troubleshooting",
            "• Ensure your CSV has a timestamp column in ISO 8601 format.\n"
            "• If no flights are detected, the tool treats the whole CSV as one flight.\n"
            "• Video must have a constant frame rate for correct OSD timing.\n"
            "• For very long flights, processing can take several minutes — be patient!\n"
            "• Settings file path: ~/.dji_osd_tool/osd_settings.json")

        tk.Frame(inner, bg=DARK_BG, height=20).pack()

    def _build_about_tab(self, p):
        """Build the About tab."""
        frame = tk.Frame(p, bg=DARK_BG)
        frame.pack(expand=True, fill="both")
        center = tk.Frame(frame, bg=DARK_BG)
        center.place(relx=0.5, rely=0.5, anchor="center")

        # Logo / title block
        logo_frame = tk.Frame(center, bg=PANEL_BG, padx=40, pady=30,
                              highlightbackground=ACCENT, highlightthickness=1)
        logo_frame.pack(pady=(0, 20))

        tk.Label(logo_frame, text="DJI Avata OSD Overlay Tool",
                 bg=PANEL_BG, fg=ACCENT, font=("sans-serif", 20, "bold")).pack()
        tk.Label(logo_frame, text="v2.2  —  GUI Edition",
                 bg=PANEL_BG, fg=MUTED_FG, font=FNB).pack(pady=(4, 16))

        tk.Frame(logo_frame, bg=MUTED_FG, height=1).pack(fill="x", pady=(0, 12))

        for line, fg in [
            ("Burns DJI telemetry OSD onto your drone footage.", TEXT_FG),
            ("Supports multi-flight detection, per-element positioning,", TEXT_FG),
            ("overlay delay for sync correction, and quality re-encoding.", TEXT_FG),
        ]:
            tk.Label(logo_frame, text=line, bg=PANEL_BG, fg=fg, font=FNS).pack()

        tk.Frame(logo_frame, bg=MUTED_FG, height=1).pack(fill="x", pady=(14, 10))

        # Tech stack
        stack_frame = tk.Frame(logo_frame, bg=PANEL_BG)
        stack_frame.pack()
        for lib in ["Python 3", "OpenCV", "pandas", "NumPy", "tkinter"]:
            tk.Label(stack_frame, text=lib, bg=SEL_BG, fg=ACCENT2,
                     font=FNS, padx=8, pady=3, relief="flat").pack(
                         side="left", padx=4, pady=2)

        # Info rows below the box
        info_frame = tk.Frame(center, bg=DARK_BG)
        info_frame.pack(pady=12)
        for label, value in [
            ("Settings file:",  str(SETTINGS_FILE)),
            ("Python:",         sys.version.split()[0]),
            ("OpenCV:",         cv2.__version__),
            ("ffmpeg:",         FFMPEG if FFMPEG else "not found"),
        ]:
            row = tk.Frame(info_frame, bg=DARK_BG); row.pack(fill="x", pady=1)
            tk.Label(row, text=label, bg=DARK_BG, fg=MUTED_FG, font=FNS,
                     width=14, anchor="e").pack(side="left")
            tk.Label(row, text=value, bg=DARK_BG, fg=TEXT_FG, font=FNM).pack(side="left", padx=6)

        tk.Label(center,
                 text="Open source. Use freely. Share your flights!",
                 bg=DARK_BG, fg=MUTED_FG, font=FNS).pack(pady=(8, 0))

    def _load_csv(self):
        path = filedialog.askopenfilename(
            title="Open Telemetry CSV",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if not path: return
        self.csv_path = path
        self.csv_label.configure(text=Path(path).name, fg=TEXT_FG)
        self._log(f"Loading: {path}", "info")
        self._detect_flights(path)

    def _detect_flights(self, path):
        try:
            df = pd.read_csv(path)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        except Exception as e:
            self._log(f"Error reading CSV: {e}", "err"); return
        if "camera.state.record_state" not in df.columns:
            self._log("WARNING: no 'camera.state.record_state' — treating all rows as one flight", "warn")
            df["camera.state.record_state"] = 2
        self.flights = detect_flights(df)
        self._clear_flight_cards()
        if not self.flights:
            self._log("No recording periods found.", "err")
            self._no_fl.configure(text="No flights found.\nCheck CSV format.")
            self._no_fl.pack(pady=30); return
        self._no_fl.pack_forget()
        self._log(f"Found {len(self.flights)} flight(s).", "ok")
        for f in self.flights:
            m, s = int(f["duration_s"]//60), int(f["duration_s"]%60)
            self._log(f"  Flight {f['index']+1}: {f['start'].strftime('%H:%M:%S')}  "
                      f"{m:02d}:{s:02d}  alt={f['alt_max']:.0f}m  "
                      f"batt {f['batt_start']}->{f['batt_end']}%")
        for flight in self.flights:
            card = FlightCard(self.flights_inner, flight, on_select=self._select_flight,
                              relief="flat", highlightbackground=MUTED_FG, highlightthickness=1)
            card.pack(fill="x", pady=(0,5))
            self.flight_cards.append(card)
        self._select_flight(self.flights[0])

    def _clear_flight_cards(self):
        for c in self.flight_cards: c.destroy()
        self.flight_cards.clear(); self.selected_flight = None
        self._no_fl.pack(pady=30)

    def _select_flight(self, flight):
        self.selected_flight = flight
        for card in self.flight_cards:
            card.set_selected(card.flight is flight)
        for w in self.detail_frame.winfo_children(): w.destroy()
        f = flight; m, s = int(f["duration_s"]//60), int(f["duration_s"]%60)
        for label, value in [
            ("Flight",    f"{f['index']+1} of {len(self.flights)}"),
            ("Date",      f["start"].strftime("%Y-%m-%d")),
            ("Start",     f["start"].strftime("%H:%M:%S")),
            ("Duration",  f"{m:02d}:{s:02d}"),
            ("Samples",   f"{f['samples']} @ ~{f['samples']/max(f['duration_s'],1):.1f} Hz"),
            ("Max Alt",   f"{f['alt_max']:.1f} m"),
            ("Max Speed", f"{f['speed_max']:.1f} m/s  ({f['speed_max']*3.6:.1f} km/h)"),
            ("Battery",   f"{f['batt_start']}% -> {f['batt_end']}%"),
        ]:
            row = tk.Frame(self.detail_frame, bg=PANEL_BG); row.pack(fill="x", padx=10, pady=1)
            tk.Label(row, text=label+":", bg=PANEL_BG, fg=MUTED_FG, font=FNS, width=12, anchor="w").pack(side="left")
            tk.Label(row, text=value, bg=PANEL_BG, fg=TEXT_FG, font=FNS).pack(side="left")
        if self.csv_path:
            stem = Path(self.csv_path).stem
            suggested = str(Path(self.csv_path).parent / f"{stem}_flight{f['index']+1}_osd.mp4")
            self.out_entry.delete(0,"end"); self.out_entry.insert(0, suggested)
        self._run_sync_check(); self._update_process_btn()

    def _browse_video(self):
        path = filedialog.askopenfilename(
            title="Select Video",
            filetypes=[("Video","*.mp4 *.MP4 *.mov *.avi *.mkv"),("All","*.*")])
        if not path: return
        self.vid_entry.delete(0,"end"); self.vid_entry.insert(0, path)
        self._run_sync_check(); self._update_process_btn()

    def _browse_output(self):
        ini = self.out_entry.get() or "output.mp4"
        path = filedialog.asksaveasfilename(title="Save Output",
            defaultextension=".mp4", initialfile=Path(ini).name,
            initialdir=str(Path(ini).parent), filetypes=[("MP4","*.mp4"),("All","*.*")])
        if path: self.out_entry.delete(0,"end"); self.out_entry.insert(0, path)

    def _run_sync_check(self):
        vid = self.vid_entry.get().strip()
        if not self.selected_flight or not vid:
            self.sync_result.configure(text="Pick a video to check sync.", fg=MUTED_FG); return
        if not os.path.exists(vid):
            self.sync_result.configure(text="Video file not found.", fg=WARN_COL); return
        info = get_video_info(vid)
        if not info:
            self.sync_result.configure(text="Cannot read video.", fg=WARN_COL); return
        td = self.selected_flight["duration_s"]; vd = info["duration"]
        diff = abs(td - vd)
        tm, ts = int(td//60), int(td%60); vm, vs = int(vd//60), int(vd%60)
        lines = (f"Telemetry: {tm:02d}:{ts:02d} ({td:.1f}s)   "
                 f"Video: {vm:02d}:{vs:02d} ({vd:.1f}s)   Delta: {diff:.1f}s\n"
                 f"Resolution: {info['width']}x{info['height']}   "
                 f"FPS: {info['fps']:.2f}   Frames: {info['frames']:,}")
        if diff < 2:   txt, col = "Sync looks great.", ACCENT2
        elif diff < 5: txt, col = "Moderate mismatch — should still work.", HIGHLIGHT
        else:          txt, col = f"Large mismatch ({diff:.1f}s) — wrong clip?", WARN_COL
        self.sync_result.configure(text=lines+"\n"+txt, fg=col)
        self._log(f"Sync check: tel={td:.1f}s  vid={vd:.1f}s  delta={diff:.1f}s",
                  "ok" if diff<2 else "warn" if diff<5 else "err")

    def _update_process_btn(self):
        vid = self.vid_entry.get().strip(); out = self.out_entry.get().strip()
        ok  = bool(self.selected_flight and vid and os.path.exists(vid) and out)
        self.process_btn.configure(state="normal" if ok else "disabled")

    def _open_osd_editor(self):
        OSDEditorWindow(self, self.osd_settings)

    def _save_delay(self):
        try:
            val = float(self._delay_var.get())
        except (ValueError, tk.TclError):
            val = 0.0
        self._delay_var.set(round(val, 2))
        self.osd_settings.set_overlay_delay(val)
        self.osd_settings.save()
        self._log(f"Overlay delay set to {val:.2f}s", "info")

    def _start_processing(self):
        if self._processing: return
        vid = self.vid_entry.get().strip(); out = self.out_entry.get().strip()
        if not vid or not os.path.exists(vid):
            messagebox.showerror("Error","Video file not found."); return
        if not out:
            messagebox.showerror("Error","Specify an output file."); return
        self._processing  = True
        self._cancel_flag = threading.Event()
        self.process_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.progress_var.set(0)
        try:
            delay = float(self._delay_var.get())
        except (ValueError, tk.TclError):
            delay = 0.0
        self._log(f"Starting overlay generation -> {out}  (delay={delay:+.2f}s)", "info")
        fdf = self.selected_flight["df"].copy()
        q   = self._proc_queue; cf = self._cancel_flag
        settings = self.osd_settings

        def worker():
            try:
                ov = DJIOSDOverlay(vid, fdf, out, osd_settings=settings,
                                   progress_cb=lambda p,m: q.put(("progress",p,m)),
                                   overlay_delay=delay)
                ok = ov.run(cancel_flag=cf)
                q.put(("done" if ok else "cancelled", 100 if ok else 0,
                       f"Saved to: {out}" if ok else "Cancelled."))
            except Exception as e:
                import traceback
                q.put(("error", 0, f"{e}\n{traceback.format_exc()}"))

        threading.Thread(target=worker, daemon=True).start()

    def _cancel_processing(self):
        if hasattr(self, "_cancel_flag"): self._cancel_flag.set()
        self.cancel_btn.configure(state="disabled")
        self._log("Cancel requested...", "warn")

    def _poll_queue(self):
        try:
            while True:
                kind, pct, text = self._proc_queue.get_nowait()
                if kind == "progress":
                    self.progress_var.set(pct); self.progress_label.configure(text=text)
                elif kind == "done":
                    self.progress_var.set(pct); self.progress_label.configure(text=text)
                    self._log(f"Done! {text}", "ok"); self._processing = False
                    self.process_btn.configure(state="normal")
                    self.cancel_btn.configure(state="disabled")
                    messagebox.showinfo("Done", f"Overlay complete!\n\n{text}")
                elif kind in ("cancelled","error"):
                    self.progress_label.configure(text=text)
                    self._log(text, "warn" if kind=="cancelled" else "err")
                    self._processing = False
                    self.process_btn.configure(state="normal")
                    self.cancel_btn.configure(state="disabled")
                    if kind == "error": messagebox.showerror("Error", text[:400])
        except queue.Empty:
            pass

        try:
            while True:
                kind, pct, text = self._q_queue.get_nowait()
                if kind == "progress":
                    self.q_prog_var.set(pct); self.q_prog_lbl.configure(text=text)
                elif kind == "done":
                    self.q_prog_var.set(100); self.q_prog_lbl.configure(text=text)
                    self._q_proc = False
                    self.q_run_btn.configure(state="normal")
                    self.q_cancel_btn.configure(state="disabled")
                    out = self.q_out_entry.get().strip()
                    size_mb = os.path.getsize(out)/1024/1024 if os.path.exists(out) else 0
                    messagebox.showinfo("Done", f"Compression complete!\n{text}\nFile size: {size_mb:.1f} MB")
                elif kind in ("cancelled","error"):
                    self.q_prog_lbl.configure(text=text)
                    self._q_proc = False
                    self.q_run_btn.configure(state="normal")
                    self.q_cancel_btn.configure(state="disabled")
                    if kind == "error": messagebox.showerror("Error", text[:400])
        except queue.Empty:
            pass

        self.after(100, self._poll_queue)

    def _log(self, msg, tag=""):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg+"\n", tag)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _q_browse_input(self):
        path = filedialog.askopenfilename(
            title="Select Input Video",
            filetypes=[("Video","*.mp4 *.MP4 *.mov *.avi *.mkv"),("All","*.*")])
        if not path: return
        self.q_in_entry.delete(0,"end"); self.q_in_entry.insert(0, path)
        p = Path(path)
        self.q_out_entry.delete(0,"end")
        self.q_out_entry.insert(0, str(p.parent / (p.stem + "_compressed" + p.suffix)))
        self._q_update_estimate()

    def _q_browse_output(self):
        ini = self.q_out_entry.get() or "compressed.mp4"
        path = filedialog.asksaveasfilename(title="Save Compressed Video",
            defaultextension=".mp4", initialfile=Path(ini).name,
            initialdir=str(Path(ini).parent), filetypes=[("MP4","*.mp4"),("All","*.*")])
        if path: self.q_out_entry.delete(0,"end"); self.q_out_entry.insert(0, path)

    def _q_update_estimate(self):
        src = self.q_in_entry.get().strip()
        if not src or not os.path.exists(src):
            self.q_estimate.configure(text=""); return
        info = get_video_info(src)
        if not info: return
        res_name = self.q_res_var.get()
        res  = next((r for r in RESOLUTION_PRESETS if r[0]==res_name), RESOLUTION_PRESETS[0])
        w    = res[1] or info["width"]; h = res[2] or info["height"]
        crf  = next((q[1] for q in QUALITY_PRESETS if q[0]==self.q_qual_var.get()), 26)
        est  = estimate_size_mb(info["duration"], crf, w, h)
        orig = os.path.getsize(src)/1024/1024
        self.q_estimate.configure(
            text=f"Original: {orig:.0f} MB\nEstimated: ~{est:.0f} MB\n({info['duration']:.0f}s, {w}x{h})",
            fg=ACCENT2 if est < orig else HIGHLIGHT)

    def _q_start(self):
        if self._q_proc: return
        src = self.q_in_entry.get().strip(); dst = self.q_out_entry.get().strip()
        if not src or not os.path.exists(src):
            messagebox.showerror("Error","Input video not found."); return
        if not dst:
            messagebox.showerror("Error","Specify output file."); return
        if src == dst:
            messagebox.showerror("Error","Input and output must differ."); return
        res_name = self.q_res_var.get()
        res  = next((r for r in RESOLUTION_PRESETS if r[0]==res_name), RESOLUTION_PRESETS[0])
        crf  = next((q[1] for q in QUALITY_PRESETS if q[0]==self.q_qual_var.get()), 26)
        w, h = res[1], res[2]
        self._q_proc = True
        self._q_cancel = threading.Event()
        self.q_run_btn.configure(state="disabled")
        self.q_cancel_btn.configure(state="normal")
        self.q_prog_var.set(0); self.q_prog_lbl.configure(text="Starting...")
        q = self._q_queue; cf = self._q_cancel

        def worker():
            fn = run_ffmpeg_compress if FFMPEG else run_opencv_compress
            ok, msg = fn(src, dst, crf, w, h, cf,
                         progress_cb=lambda p,m: q.put(("progress",p,m)))
            kind = "done" if ok else "cancelled" if "Cancelled" in msg else "error"
            q.put((kind, 0, msg))

        threading.Thread(target=worker, daemon=True).start()

    def _q_cancel(self):
        self._q_cancel.set()
        self.q_cancel_btn.configure(state="disabled")
        self.q_prog_lbl.configure(text="Cancelling...")


# ═════════════════════════════════════════════════════════════════════════════
#  CLI
# ═════════════════════════════════════════════════════════════════════════════
def cli_main():
    import argparse
    parser = argparse.ArgumentParser(description="DJI Avata OSD Overlay CLI")
    sub = parser.add_subparsers(dest="cmd")
    ov = sub.add_parser("overlay")
    ov.add_argument("video"); ov.add_argument("csv"); ov.add_argument("output")
    ov.add_argument("--flight", type=int, default=1)
    ck = sub.add_parser("check")
    ck.add_argument("video"); ck.add_argument("csv")
    ck.add_argument("--flight", type=int, default=1)
    args = parser.parse_args()
    if not args.cmd: parser.print_help(); return
    df = pd.read_csv(args.csv); df["timestamp"] = pd.to_datetime(df["timestamp"])
    flights = detect_flights(df)
    if not flights: print("No recording periods found."); sys.exit(1)
    fi = args.flight - 1
    if fi >= len(flights): print(f"Flight {args.flight} not found."); sys.exit(1)
    f = flights[fi]
    if args.cmd == "check":
        info = get_video_info(args.video)
        if not info: print("Cannot open video."); sys.exit(1)
        diff = abs(f["duration_s"] - info["duration"])
        print(f"Telemetry: {f['duration_s']:.1f}s  Video: {info['duration']:.1f}s  Delta: {diff:.1f}s")
        print("OK" if diff<2 else "WARN" if diff<5 else "MISMATCH")
    elif args.cmd == "overlay":
        settings = OSDSettings()
        ov = DJIOSDOverlay(args.video, f["df"], args.output, osd_settings=settings,
                           progress_cb=lambda p,m: print(f"\r{m}", end="", flush=True))
        ov.run(); print()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("overlay","check"):
        cli_main()
    else:
        App().mainloop()
