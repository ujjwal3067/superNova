#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import logging
from logging import DEBUG, FileHandler
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
DEBUG = True
configFile = ""
config = {}
sharedDir = ""
FileList = []
requested = ""

signal.signal(signal.SIGINT, sigint_handler)


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
        transmitMessageToPeer(tracker, "IWANT " + user + "\n\0")
        # we are recursively sending the previous command so that peer rememeber it's last commnad
        # for the next sequential step
        return makeConnection(tracker, inputStream, "IWANT")

    elif command == "WELCOME":
        user = fields[1]
        config["user"] = user
        json_save(configFile, config)
        return None, inputStream  # TODO error fixed

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
    sharedDir = ""
    while not os.path.isdir(sharedDir):
        print()
        print("Enter Path of the directory to connect to the P2P network ")
        print("<< warning :: Other peers can have access to these files>>")
        sharedDir = raw_input()
        # if the path is not a dir or the path doesn't exists
        # ask again
        if not os.path.isdir(sharedDir):
            print("not a directory : please enter valid path")
    return sharedDir


def Peer(socketConnection, address):
    # method is used to connect the other Peer in the network
    global sharedDir
    inputStream = ""
    while True:
        # try to make connection
        while "\0" not in inputStream:
            inputStream += socketConnection.recv(4096)
        # connection is made
        print("connection established with the peer")
        index = inputStream.index("\0")
        msg = inputStream[0:index - 1]
        inputStream = inputStream[index+1:]
        logging.info("message received : " + msg)
        fields = msg.split()
        # extract the command out of inputStream buffer string
        command = fields[0]

        # *processing request

        if command == "GIVE":
            fileSharing = sharedDir + "/" + fields[1]
            # go to the path of the file the other peer wants
            if os.path.isfile(fileSharing):
                fileSharingSIZE = os.path.getsize(fileSharing)  # file size
                transmitMessageToPeer(
                    socketConnection, "TAKE {}\n\0".format(str(fileSharingSIZE)))
                # preparing the the file to send away
                fileSharingSEND = open(fileSharing, "rb")
                fileREADER = ""
                # read the first 1024 bytes of the file
                fileREADER = fileSharingSEND.read(1024)
                # this method will print the contents of the file on the console
                #! remove it later
                while fileREADER:
                    # print("sending-->" + fileREADER)
                    socketConnection.send(fileREADER)
                    fileREADER = fileSharingSEND.read(1024)
                logging.info("file {} SENT to the peer".format(fileSharing))
                fileSharingSEND.close()
            else:
                transmitMessageToPeer(socketConnection, "ERROR\n\0")
                socketConnection.close()
                break
        elif command == "THANKS":
            socketConnection.close()
            break
        else:
            transmitMessageToPeer(socketConnection, "ERROR\n\0")
            socketConnection.close()
            break
    return


# reponsible for making connection to new incoming peers
def incomingPeerConnections(peerIP, peerPORT, queue):
    try:
        incomingSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except socket.error:
        logging.error("socket.socket error")
        sys.exit(-1)

    try:
        incomingSocket.bind((peerIP, peerPORT))
    except socket.error:
        logging.error("port {} is use already".format(incomingSocket))
        sys.exit(-1)
    # server connection for listening for incoming peer connections
    incomingSocket.listen(5)
    logging.info("client listening on {}:{}".format(peerIP, str(peerPORT)))
    #! possible ERROR
    incomingPeerConnectionPORT = incomingSocket.getsockname()[1]
    queue.put((peerIP, peerPORT))
    peerCount = 0
    while True:
        # keep listening for incoming request
        socketConnection, address = incomingSocket.accept()
        logging.info("Peer connected with address {}:{}".format(
            address[0], str(address[1])))

        # calling Peer method in separete thread so that main thread doesn't  have to wait for one Peer to finish
        newPeerThread = Thread(name="peer {}".format(
            peerCount), target=Peer, args=(socketConnection, address))
        # put it in background
        newPeerThread.daemon = True
        newPeerThread.start()
        # new peer is finally connected
        print("new peer thread started")
        peerCount += 1


def getFile(peer):
    global requested
    print()
    print("file name: ")
    requested = raw_input()
    # ask for the file from the other peer
    transmitMessageToPeer(peer, "GIVE {}\n\0".format(requested))
    inputStream = ""
    while "\0" not in inputStream:
        inputStream += peer.recv(4096)
    index = inputStream.index("\0")
    msg = inputStream[0:index - 1]
    inputStream = inputStream[index+1:]
    logging.info("message received : " + msg)
    fields = msg.split()
    # extract the command
    command = fields[0]
    # if the command is take that means other peer has sent you a file
    if command == "TAKE":
        file_size = fields[1]
        # read and create a new file foryourself
        while len(inputStream) < int(file_size):
            inputStream += peer.recv(4096)
        newFileWriter = open(sharedDir + "/" + requested, "wb")
        newFileWriter.write(inputStream)
        newFileWriter.close()
        logging.info("file {} recieved".format(requested))
        transmitMessageToPeer(peer, "THANKS\n\0")
        peer.close()
    elif command == "ERROR":
        return
    else:
        logging.warning("an invalid")
        sys.exit(-1)


def main():
    global config
    global configFile
    global FileList
    global sharedDir
    logging.basicConfig(level=logging.DEBUG,
                        format="[%(levelname)s] (%(threadName)s) %(message)s",
                        filename="client.log",
                        filemode="w")
    console = logging.StreamHandler()
    # TODO not doing debug anymore
    if DEBUG:
        console.setLevel(logging.DEBUG)
    else:
        console.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "[%(levelname)s] (%(threadName)s) %(message)s")
    console.setFormatter(formatter)
    logging.getLogger("").addHandler(console)

    configFile = "config.json"

    print("Welcome to the SuperNOVA network")
    if os.path.isfile(configFile):
        config = json_load(configFile)
    else:
        # else new server config file in json format
        config["trackerIP"] = "localhost"
        #!todo change the port
        config["trackerPort"] = 45000
        config["peerListeningIP"] = "localhost"
        config["peerListeningPORT"] = 0
        config["sharedDIR"] = getSharedDIR()
        json_save(configFile, config)

    logging.debug("configuration : " + str(config))

    sharedDir = config["sharedDIR"]

    avFile = [avfile for avfile in os.listdir(
        sharedDir) if os.path.isfile(os.path.join(sharedDir, avfile))]

    # logging.debug("list of files avaialble for sharing is" + str(avFile))

    print("available files are {}".format(str(avFile)))

    trackerAdd = (config["trackerIP"], config["trackerPort"])
    # connect this peer with tracker
    print("printing tracker information")
    print(trackerAdd)  # gives correct addresss of tracker
    tracker = InitializeConnection(trackerAdd)  # !error

    print("connection is done")
    inputStream = ""
    if "user" in config:
        # if the user already in the list ( tracker list)
        transmitMessageToPeer(tracker, "HELLO " + config["user"] + "\n\0")
    else:
        # else this means this is peer's first time connecting to tracker
        transmitMessageToPeer(tracker, "HELLO\n\0")
    data, inputStream = makeConnection(tracker, inputStream, "HELLO")
    peerListeningIP = config["peerListeningIP"]
    peerListeningPORT = config["peerListeningPORT"]
    queue = Queue.Queue()
    PeerconnectionListeningThread = Thread(name="PeerConnectionThread", target=incomingPeerConnections, args=(
        peerListeningIP, peerListeningPORT, queue))
    PeerconnectionListeningThread.daemon = True  # send the thread to background
    PeerconnectionListeningThread.start()
    peerListeningIP, peerListeningPORT = queue.get()
    PeerMsg = "LISTENING {} {}\n\0".format(peerListeningIP, peerListeningPORT)
    transmitMessageToPeer(tracker, PeerMsg)
    makeConnection(tracker, inputStream, "LISTENING")
    print("this peer is all setup and listening for incoming peer connections")

    msg_list = "LIST {}\n".format(len(avFile))
    for avfile in avFile:
        msg_list += avfile + "\n"
    msg_list += "\0"
    transmitMessageToPeer(tracker, inputStream, "LIST")

    transmitMessageToPeer(tracker, "SENDLIST" + "\n\0")
    makeConnection(tracker, inputStream, "SENDLIST")

    # MENU
    while True:
        print()
        print("Available commands")
        print("1: request the list of peers and files available")
        print("2: Check the address and port  of the peer ")
        print("3: new sharing Dir")
        print("4: exit the superNOVA P2P network")
        command = raw_input()
        if command == "1":
            transmitMessageToPeer(tracker, "SENDLIST" + "\n\0")
            makeConnection(tracker, inputStream, "SENDLIST")
        elif command == "2":
            print(" specify the peer for address")
            while True:
                peerName = raw_input()
                if peerName == config["user"]:
                    print("{} try again. :: it's your username".format(peerName))
                    continue
                if peerName in [output.split()[0] for output in FileList]:
                    break
                print("{} is an invalid peer name :: TRY AGAIN".format(peerName))
            transmitMessageToPeer(tracker, "WHERE" + peerName + "\n\0")
            (peerIP, peerPORT), inputStream = makeConnection(
                tracker, inputStream, "WHERE")

            # print("peerIP is {}".format(peerIP))

            peer = InitializeConnection((peerIP, peerPORT))
            # get the file from the peer
            getFile(peer)
        elif command == "3":
            config["sharingDIR"] = getSharedDIR()
            json_save(configFile, config)
        elif command == "4":
            print("Thanks for using superNOVA p2p network")
            print("... exiting the program")
            sys.exit(0)
        else:
            print("invalid command :: TRY AGAIN ")


# run this as a script
if __name__ == "__main__":
    main()
