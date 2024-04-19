#!/usr/bin/python3
# SPDX-FileCopyrightText: 2024 Luca Weiss
# SPDX-License-Identifier: MIT

import os
import json
import subprocess
import sys
from pprint import pprint
from typing import Optional

DEBUG = False

# Run against slot 2 (normally the eEUICC slot)
# TODO: Allow running against other slot also
SLOT = 2

# apdu request doesn't provide us the channel_id again, so we need to persist it
CHANNEL_ID: Optional[int] = None


class QmicliException(Exception):
    pass


def run_qmicli(command: str) -> str:
    try:
        output = (
            subprocess.check_output(
                [
                    "qmicli",
                    "-d", "qrtr://0",
                    command
                ],
                stderr=subprocess.STDOUT,
            )
            .decode('utf-8')
            .strip()
        )
        return output
    except subprocess.CalledProcessError as ex:
        print("+++ LIBQMI EXCEPTION! +++")
        if ex.output:
            print(ex.output.decode('utf-8'))
        if ex.stderr:
            print(ex.stderr.decode('utf-8'))
        print(ex)
        print("+++ LIBQMI EXCEPTION! +++")
        raise QmicliException(ex) from ex


def send_apdu(apdu: str) -> str:
    return (
        run_qmicli(f"--uim-send-apdu={SLOT},{CHANNEL_ID},{apdu}")
        .replace("Send APDU operation successfully completed: ", "")
        .replace(":", "")
    )


def open_channel(aid: str) -> int:
    channel_id = (
        run_qmicli(f"--uim-open-logical-channel={SLOT},{aid}")
        .replace("Open Logical Channel operation successfully completed: ", "")
    )
    return int(channel_id)


def close_channel(channel_id: int) -> None:
    run_qmicli(f"--uim-close-logical-channel={SLOT},{channel_id}")


def handle_type_apdu(func: str, param: str):
    if func == "connect":
        # Nothing to do
        print("INFO: Connect")
        return {"ecode": 0}

    if func == "disconnect":
        # Nothing to do
        print("INFO: Disconnect")
        return {"ecode": 0}

    if func == "logic_channel_open":
        print(f"INFO: Open channel with AID {param}")
        try:
            channel_id = open_channel(param)
            # We need to persist the channel ID for send_apdu
            global CHANNEL_ID
            CHANNEL_ID = channel_id
            return {"ecode": channel_id}
        except QmicliException:
            return {"ecode": "-1"}

    if func == "logic_channel_close":
        try:
            print(f"INFO: Close channel {param}")
            close_channel(int(param))
            return {"ecode": 0}
        except QmicliException:
            return {"ecode": "-1"}

    if func == "transmit":
        try:
            if DEBUG:
                print(f"Send APDU: {param}")
            data = send_apdu(param)
            if DEBUG:
                print(f"Recv APDU: {data}")
            return {"ecode": 0, "data": data}
        except QmicliException:
            return {"ecode": "-1"}

    raise RuntimeError(f"Unhandled func {func}")


def main():
    if os.environ.get("DEBUG") == "1":
        global DEBUG
        DEBUG = 1

    env = os.environ.copy()
    env["APDU_INTERFACE"] = "libapduinterface_stdio.so" # lpac v1.x, can be removed at some point
    env["LPAC_APDU"] = "stdio" # lpac v2.x

    cmd = ['lpac'] + sys.argv[1:]
    with subprocess.Popen(cmd,
                          stdout=subprocess.PIPE,
                          stdin=subprocess.PIPE,
                          stderr=subprocess.DEVNULL,
                          env=env,
                          text=True) as proc:
        while proc.poll() is None:
            # Read a line from lpac
            line = proc.stdout.readline().strip()
            if DEBUG:
                print(f"recv={line}")
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.decoder.JSONDecodeError:
                print("Failed to decode JSON:")
                print(line)
                continue

            req_type = req["type"]
            if req_type == "lpa":
                print("INFO: Received LPA data. Printing...")
                pprint(req)
                continue

            if req_type == "progress":
                print("INFO: Received progress. Printing...")
                pprint(req)
                continue

            if req_type == "apdu":
                payload = handle_type_apdu(req["payload"]["func"], req["payload"]["param"])
                resp = {"type": "apdu", "payload": payload}
                # Send a line to lpac
                if DEBUG:
                    print(f"send={json.dumps(resp)}")
                proc.stdin.write(json.dumps(resp) + "\n")
                proc.stdin.flush()
                continue

            raise RuntimeError(f"Unknown request type {req_type}")

        print(f"Exit code: {proc.returncode}")


if __name__ == '__main__':
    main()
