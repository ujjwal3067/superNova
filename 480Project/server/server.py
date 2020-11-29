#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author : ujjwal Kumar
# student ID : 260730680
from __future__ import print_function
from ast import NodeTransformer
import json
import logging
import os
import signal
import socket
import sys
from threading import Thread

from library.library import sigint_handler
from library.library import json_load
from library.library import json_save
from library.library import transmitMessageToPeer

# json file
configFile = ""
# dictionary to maintain the config of the server
config = {}
peersFile = ""
peers = {}
connectedPeers = {}
signal.signal(signal.SIGINT, sigint_handler)


def makeConnection(connection, peer, inputStream, prevCommand):
    global configFile
    global config
    global peersFile
    global peers
    global connectedPeers
    if "\0" not in inputStream:
        return "", prevCommand
    else:
        index = inputStream.index("\0")
        msg = inputStream[0:index - 1]
        inputStream = inputStream[index+1:]
    logging.info("Message from Peer: " + str(msg))
    # split the msg from peer
    lines = msg.split("\n")
    fields = lines[0].split()
    command = fields[0]

    if command == "HELLO":
        if len(fields) == 1:
            config["userOffset"] += 1
            json_save(configFile, config)
            # keep the counter for default username
            # TODO :: change to peer_i
            user = "u{}".format(config["userOffset"])
            transmitMessageToPeer(connection, "AVAILABLE" + user + "\n\0")
            return makeConnection(connection, peer, inputStream, "AVAILABLE")
        else:
            user = fields[1]
            if user in peers:
                connectedPeers[peer] = user
                # //TODO MISSED  a debug statement here
                transmitMessageToPeer(connection, "WELCOME" + user + "\n\0")
                return makeConnection(connection, peer, inputStream, "WELCOME")
            else:
                # send error message " cannot find the username"
                transmitMessageToPeer(connection, "ERROR\n\0")
                return inputStream, "ERROR"
    elif command == "IWANT":
        user = fields[1]
        if user in peers:
            config["userOffset"] += 1
            json_save(configFile, config)
            # ? default name TODO : change it to Peer
            user = "u{}".format(config["userOffset"])
            transmitMessageToPeer(connection, "AVAILABLE"+user + "\n\0")
            return makeConnection(connection, peer, inputStream, "AVAILABLE")
        else:
            peers[user] = {"files": [],
                           "listeningIP": "",
                           "listeningPORT": None}
            json_save(peersFile, peers)
            connectedPeers[peer] = user
            transmitMessageToPeer(connection, "WELCOME" + user + "\n\0")
            return inputStream, "WELCOME"
    elif command == "LISTENING":
        peers[connectedPeers[peer]]["listeningIP"] = fields[1]
        peers[connectedPeers[peer]]["listeningPORT"] = fields[2]
        json_save(peersFile, peers)
        transmitMessageToPeer(connection, "OK\n\0")
        return inputStream, "OK"
    elif command == "LIST":
        filesCount = int(fields[1])
        if filesCount != (len(lines) - 1):
            transmitMessageToPeer("invalid command : wrong number of files")
            sys.exit(-1)
        else:
            peers[connectedPeers[peer]]["files"] = lines[1:]
            json_save(peersFile, peers)  # save the file back
        transmitMessageToPeer(connection, "OK\n\0")
        return inputStream, "OK"

    elif command == "SENDLIST":
        totalFilesCount = 0
        for peer_ in peers:
            totalFilesCount += len(peers[peer_]["files"])
        fullmsg = "FULLLIST {}\n".format(totalFilesCount)
        # make the list of all the files available
        for peer_ in peers:
            for peerfile in peers[peer_]["files"]:
                fullmsg += peer_ + " " + peerfile + "\n"
        fullmsg += "\0"
        transmitMessageToPeer(connection, fullmsg)
        return makeConnection(connection, peer, inputStream, "FULLLIST")

    elif command == "WHERE":
        peer = fields[1]
        if peer in peers:
            peerIP = peers[peer]["listeningIP"]
            peerPORT = peers[peer]["listeningPORT"]
            outputmsg = "AT {} {}\n\0".format(peerIP, peerPORT)
            transmitMessageToPeer(connection, outputmsg)
            return inputStream, "WHERE"
        else:
            transmitMessageToPeer(connection, "UNKNOWN\n\0")
            return inputStream, "UNKNOWN"

    elif command == "ERROR":
        print("error in connection :: ")
        print("shutting down superNOVA p2p network")
        sys.exit(-1)
    else:
        print("invalid command from peer")
        sys.exit(-1)
