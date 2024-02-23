#!/usr/bin/python3

import os
import json
import subprocess
import sys
from pprint import pprint

def send_apdu(data):
    # Run against slot 2, logical channel 2
    # FIXME: This channel should be opened and closed in their functions and the value used here
    # Not quite sure how to handle slot id, could have this as extra parameter for this script
    output = (
        subprocess.check_output(
            [
                "./libqmi/builddir/src/qmicli/qmicli",
                "-d", "qrtr://0",
                "--uim-send-apdu=2,2," + data
            ],
            stderr=subprocess.STDOUT,
        )
        .decode('utf-8')
        .strip()
        .replace("Send APDU operation successfully completed: ", "")
        .replace(" ", "")
    )
    return output


def handle_type_apdu(func, param):
    if func == "connect":
        # Nothing to do
        print("INFO: Connect")
        return {"ecode": 0}
    if func == "disconnect":
        # Nothing to do
        print("INFO: Disconnect")
        return {"ecode": 0}
    if func == "logic_channel_open":
        # FIXME Open channel
        print(f"INFO: Open channel with AID {param}")
        return {"ecode": 0} # TODO: Return value seems to be channel ID
    if func == "logic_channel_close":
        # FIXME Close channel
        print(f"INFO: Close channel {param}")
        return {"ecode": 0}
    if func == "transmit":
        data = send_apdu(param)
        return {"ecode": 0, "data": data}

    raise RuntimeError(f"Unhandled func {func}")


def main():
    env = os.environ.copy()
    env["APDU_INTERFACE"] = "libapduinterface_stdio.so"

    cmd = ['./lpac/build/output/lpac'] + sys.argv[1:]
    with subprocess.Popen(cmd,
                          stdout=subprocess.PIPE,
                          stdin=subprocess.PIPE,
                          stderr=subprocess.DEVNULL,
                          env=env,
                          text=True) as proc:
        while proc.poll() is None:
            # Read a line from lpac
            line = proc.stdout.readline()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.decoder.JSONDecodeError:
                print("Failed to decode JSON:")
                print(line)
                break

            req_type = req["type"]
            if req_type == "lpa":
                print("INFO: Received LPA data. Printing...")
                pprint(req)
                continue
            if req_type == "apdu":
                payload = handle_type_apdu(req["payload"]["func"], req["payload"]["param"])
                resp = {"type": "apdu", "payload": payload}
            else:
                raise RuntimeError(f"Unknown request type {req_type}")

            # Send a line to lpac
            proc.stdin.write(json.dumps(resp) + "\n")
            proc.stdin.flush()

        print(f"Exit code: {proc.returncode}")


if __name__ == '__main__':
    main()
