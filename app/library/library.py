#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import sys
import logging
import json
import socket


def sigint_handler(signal, frame):
    print()
    logging.info("quit the programme :: force close ")
    sys.exit(0)


def transmitMessageToPeer(connection, message):
    try:
        connection.sendall(message)
    except socket.error:
        logging.error("erorr while sending message")
        # exit the app in faulty state
        sys.exit(-1)
    logging.info("message sent to the client")


def json_load(jsonFile):
    with open(jsonFile, "rb") as filewriter:
        jsonObj = json.load(filewriter)
    return jsonObj


def json_save(jsonFile, jsonObj):
    with open(jsonFile, "wb+") as filewriter:
        json.dump(jsonObj, filewriter, sort_keys=True,
                  indent=4, separators=(",", ": "))


def workingFile():
    print("yes library is working now")


if __name__ == "__main__":
    print("ERROR")
    print("don't run this file as script")
