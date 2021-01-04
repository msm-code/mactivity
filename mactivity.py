#!/usr/bin/env python3

import sys
import time
import lz4.block
import json
from typing import Optional, Tuple
from pathlib import Path
import os
import subprocess
import re
from datetime import datetime


def autodiscover_firefox_state_filename() -> Path:
    return Path(
        "/home/msm/.mozilla/firefox/wg1e1zwq.default-release/sessionstore-backups/recovery.jsonlz4"
    )


def lz4json_decompress(file_obj):
    if file_obj.read(8) != b"mozLz40\0":
        raise RuntimeError("Invalid magic number")

    return lz4.block.decompress(file_obj.read())


class FirefoxState:
    def __init__(self, state_file: Path) -> None:
        with state_file.open("rb") as raw_state:
            decoded_state = lz4json_decompress(raw_state)
        self._state = json.loads(decoded_state)

    def _get_selected_window_ndx(self) -> int:
        return self._state["selectedWindow"]

    def get_active_url(self) -> Optional[str]:
        window_ndx = self._get_selected_window_ndx()

        if window_ndx <= 0:
            return None

        window_entry = self._state["windows"][window_ndx - 1]
        tab_ndx = window_entry["selected"]

        tab_entry = window_entry["tabs"][tab_ndx - 1]
        return tab_entry["entries"][0]["url"]


def load_and_dump_state(state_file: Path) -> None:
    state = FirefoxState(state_file)
    print("tab", state.get_active_url())


def get_active_window_title() -> Tuple[Optional[str], Optional[str]]:
    root = subprocess.Popen(
        ["xprop", "-root", "_NET_ACTIVE_WINDOW"], stdout=subprocess.PIPE
    )
    stdout, stderr = root.communicate()

    m = re.search(b"^_NET_ACTIVE_WINDOW.* ([\w]+)$", stdout)
    if m != None:
        window_id = m.group(1)
        window = subprocess.Popen(
            ["xprop", "-id", window_id, "WM_NAME", "WM_CLASS"], stdout=subprocess.PIPE
        )
        stdout, stderr = window.communicate()
    else:
        return None, None

    window_name = None
    match = re.search(br"WM_NAME\(\w+\) = (?P<name>.+)", stdout)
    if match != None:
        window_name = match.group("name").strip(b'"').decode()

    window_class = None
    match = re.search(br'WM_CLASS\(\w+\) = "([^"]+)", "(?P<class>[^"]+)"', stdout)
    if match != None:
        window_class = match.group("class").strip(b'"').decode()

    return window_name, window_class


def get_idle_time() -> int:
    return int(subprocess.check_output("xprintidle"))


def dump_current_state(logfile: str) -> None:
    window_name, window_class = get_active_window_title()
    idle = get_idle_time()

    timestamp = datetime.now()
    entry = {
        "timestamp": timestamp.isoformat(),
        "window_name": window_name,
        "window_class": window_class,
        "idle": idle,
    }
    print(json.dumps(entry))
    with open("log.txt", "a") as logf:
        logf.write(json.dumps(entry) + "\n")


def main():
    while True:
        logfile = sys.argv[1]
        dump_current_state(logfile)
        time.sleep(15)


if __name__ == "__main__":
    main()
