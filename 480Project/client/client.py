
from __future__ import print_function
import logging
import os
import signal
import socket
import sys
import Queue
from threading import Thread
from library.library import sigint_handler
from library.library import json_load
from library.library import json_save
from library.library import transmitMessageToPeer

# global variables
configFile = ""
config = {}
sharedDir = ""
FileList = []
requested = ""

signal.signal(singal.SIGINT, sigint_handler)


def makeConnection(tracker, inputStream, prevCommand):
    global configFile
    global FileList  # list of all the files in overlay network
    global requested  # file request by the peer

    if "\0" not in inputStream:
        inputStream += tracker.recv(4096)
        # make connection again
        return makeConnection(tracker, inputStream, prevCommand)
    else:
        index = inputStream.index("\0")
        msg = inputStream[0:index-1]
        inputStream = inputStream[index + 1:]
    logging.info("Message Received : " + msg)

    lines = msg.split("\n")
    # extracting the command from the other peer inputStream
    fields = lines[0].split()
    command = fields[0]
    if command == "AVAILABLE":
        user = fields[1]
        user = getUserName(user)
        transmitMessageToPeer(tracker, "IWANT" + user + "\n\0")
        # we are recursively sending the previous command so that peer rememeber it's last commnad
        # for the next sequential step
        return makeConnection(tracker, inputStream, "IWANT")

    elif command == "WELCOME":
        user = fields[1]
        config["user"] = user
        json_save(configFile, config)

    elif command == "FULLLIST" and prevCommand == "SENDLIST":
        filesCount = int(fields[1])
        if filesCount != (len(lines) - 1):
            logging.warning("invalid Full list of msg, wrong number of files ")
            transmitMessageToPeer(tracker, "ERROR\n\0")
            sys.exit(-1)
        else:
            FileList = lines[1:]
            print()
            print(" List of files available in the P2P network are")
            for line in lines[1:]:
                # print the name of the file
                print(line)
        return None, inputStream

    elif command == "AT" and prevCommand == "WHERE":
        peerIP = fields[1]
        peerPORT = int(fields[2])
        # return the Peer IP and Peer PORT tuple and inputStream as output
        return (peerIP, peerPORT), inputStream

    elif command == "OK" and prevCommand in ("LIST", "LISTENING"):
        return None, inputStream
    elif command == "ERROR":
        logging.warning(
            "Error: maybe connection lost with other peer and tracker")
        sys.exit(-1)

    else:
        logging.warning(
            'an invalid command was recieved: "{}"'.format(command))
        # exit the app
        sys.exit(-1)


# this method is used for making socket connection with the peer
def InitializeConnection(address):
    IP, PORT = address
    try:
        peerConnection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except socket.error:
        logging.info("error while connection to socket")
        sys.exit(-1)
    try:
        peerConnection.connect((IP, PORT))
        logging.info(
            "cannot connect to the peer or tracker {}:{} ".format(IP, PORT))
    except socket.error:
        logging.info("port connection error in during Initialization")
        sys.exit(-1)
    return peerConnection


def getUserName(OtherUser):
    print(" Enter Peer userName")
    user = raw_input()
    if user == "":
        # if user didn't specify the user name then give the default username
        user = OtherUser
    return user


def getSharedDIR():
    # this method is used to connect all the shared  DIR in the network
    # so that it can be used by everyone else
