#!/usr/bin/python3

import os
import json
import subprocess
import sys
from subprocess import Popen, PIPE
from pprint import pprint

def run_apdu(data):
    # Run against slot 2, logical channel 2
    # FIXME: This channel should be opened and closed by this wrapper
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


def handle_func(func, param):
    #print(f"INFO: func={func} param={param}")
    if func == "connect":
        # Nothing to do
        print("INFO: Connect")
        return {"ecode": 0}
    if func == "logic_channel_open":
        # FIXME Open channel
        print(f"INFO: Open channel with AID {param}")
        # TODO: Return value seems to be channel ID
        return {"ecode": 0}
    if func == "transmit":
        ret_data = run_apdu(param)
        #print("Returning APDU data: " + ret_data)
        return {"ecode": 0, "data": ret_data}
    if func == "logic_channel_close":
        # FIXME Close channel
        print(f"INFO: Close channel {param}")
        return {"ecode": 0}

    raise RuntimeError(f"Unhandled func {func}")

def handle_request(data):
    if data["type"] == "lpa":
        print("INFO: Received LPA data. Printing...")
        pprint(data)
        return None
    if data["type"] != "apdu":
        raise RuntimeError("Unknown type")
    payload = data["payload"]

    ret_payload = handle_func(payload["func"], payload["param"])
    return {"type": "apdu", "payload": ret_payload}

def main():
    env = os.environ.copy()
    env["APDU_INTERFACE"]="libapduinterface_stdio.so"

    cmd = ['./lpac/build/output/lpac'] + sys.argv[1:]
    p = Popen(cmd, stdout=PIPE, stdin=PIPE, stderr=subprocess.DEVNULL, env=env, text=True)
    while p.poll() is None:
        #print("INFO: waiting for data...")
        line = p.stdout.readline()
        if not line:
            continue

        try:
            obj = json.loads(line)
        except json.decoder.JSONDecodeError:
            print("Failed to decode JSON:")
            print(line)
            sys.exit(1)

        #print("INFO: Got data: " + str(obj))

        #resp = {"type": "apdu", "payload": {"ecode": 0}}
        resp = handle_request(obj)
        #print("INFO: Sending response: " + json.dumps(resp))
        p.stdin.write(json.dumps(resp) + "\n")
        p.stdin.flush()

if __name__ == '__main__':
    main()
