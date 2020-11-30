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

    print("got the Command {}".format(prevCommand))

    if command == "HELLO":
        if len(fields) == 1:
            config["userOffset"] += 1
            json_save(configFile, config)
            # keep the counter for default username
            # TODO :: change to peer_i
            user = "u{}".format(config["userOffset"])
            transmitMessageToPeer(connection, "AVAILABLE " + user + "\n\0")
            return makeConnection(connection, peer, inputStream, "AVAILABLE")
        else:
            user = fields[1]
            if user in peers:
                connectedPeers[peer] = user
                # //TODO MISSED  a debug statement here
                transmitMessageToPeer(connection, "WELCOME " + user + "\n\0")
                return makeConnection(connection, peer, inputStream, "WELCOME")
            else:
                # send error message " cannot find the username"
                transmitMessageToPeer(connection, "ERROR\n\0")
                return inputStream, "ERROR"

        '''
        IWANT COMMAND :##################

        '''
    elif command == "IWANT":
        user = fields[1]
        if user in peers:
            config["userOffset"] += 1
            json_save(configFile, config)
            # ? default name TODO : change it to Peer
            user = "u{}".format(config["userOffset"])
            transmitMessageToPeer(connection, "AVAILABLE "+user + "\n\0")
            return makeConnection(connection, peer, inputStream, "AVAILABLE")
        else:
            peers[user] = {"files": [],
                           "listeningIP": "",
                           "listeningPORT": None}
            json_save(peersFile, peers)
            connectedPeers[peer] = user
            transmitMessageToPeer(connection, "WELCOME " + user + "\n\0")
            return inputStream, "WELCOME"

        '''
        LISTENING COMMAND :################

        '''
    elif command == "LISTENING":
        peers[connectedPeers[peer]]["listeningIP"] = fields[1]
        peers[connectedPeers[peer]]["listeningPORT"] = fields[2]
        json_save(peersFile, peers)

        print(" peers : " + str(peers))

        transmitMessageToPeer(connection, "OK\n\0")
        return inputStream, "OK"

        '''
        LIST COMMAND :#####################

        '''
    elif command == "LIST":
        print("(int LIST ) prevCommand {} ".format(prevCommand))
        filesCount = int(fields[1])
        if filesCount != (len(lines) - 1):
            print("invalid command : wrong number of files")
            # TODO : ERROR FIXED HERE
            transmitMessageToPeer(connection, "ERROR\n\0")
            sys.exit(-1)
        else:
            peers[connectedPeers[peer]]["files"] = lines[1:]
            json_save(peersFile, peers)  # save the file back
        # send the information to the peer
        transmitMessageToPeer(connection, "OK\n\0")
        return inputStream, "OK"

        '''
        SENDLIST COMMAND :#################

        '''

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

        '''

        WHERE COMMAND :#####################

        '''

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


def PEER(connection, address):
    inputStream = ""
    prevCommand = ""
    while True:
        incomingConnectionRequest = connection.recv(4096)
        if len(incomingConnectionRequest) == 0:
            print("no connection was established")
            break
        else:
            inputStream += incomingConnectionRequest
            # try to establish a connection
            print("trying to establish Connection with peer")
        inputStream, prevCommand = makeConnection(
            connection, address, inputStream, prevCommand)
        print("Connection ESTABLISHED ....")


def main():
    print("Starting the Tracker on port 45000")
    global configFile
    global config
    global peersFile
    global peers
    # TODO : skip logging
    configFile = "config.json"
    peersFile = "peers.json"
    if os.path.isfile(configFile):
        config = json_load(configFile)  # load the server config files
    else:
        # init a new one
        config["HOST"] = "localhost"
        config["PORT"] = 45000
        config["userOffset"] = 0
        json_save(configFile, config)

    # load the connected peers  from json file
    if os.path.isfile(peersFile):
        peers = json_load(peersFile)
    else:
        json_save(peersFile, peers)

    try:
        serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except socket.error:
        print("error in server socket")
        print("exiting the shuting down the tracker .....")
        print("Tracker/Server is down.. ")
        print("Please try to restart ...")
        sys.exit(-1)

    host = config["HOST"]
    port = config["PORT"]

    try:
        serverSocket.bind((host, port))
    except socket.error:
        print("There was an error while setuping the server socket")
        print("Existing superNOVA bootUP Stage")
        sys.exit(-1)

    # listening from incoming connection from peer on the server socket
    serverSocket.listen(5)
    peerCounter = 0
    while True:
        connection, address = serverSocket.accept()
        peerThread = Thread(name="peer {}".format(
            peerCounter), target=PEER, args=(connection, address))
        peerThread.daemon = True
        peerThread.start()
        peerCounter += 1


if __name__ == "__main__":
    main()
