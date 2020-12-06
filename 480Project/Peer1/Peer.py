#!/usr/bin/env python
# -*- coding: utf-8 -*-


from __future__ import print_function
import os
import signal
import socket
import sys
import Queue
import json
from threading import Thread


def sigint_handler(signal, frame):
    print()
    sys.exit(0)


def transmitMessageToPeer(connection, message):
    try:
        connection.sendall(message)
    except socket.error:
        sys.exit(-1)


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


# global variables
configFile = ""
config = {}
sharedDir = ""
FileList = []
requested = ""

signal.signal(signal.SIGINT, sigint_handler)


def makeConnection(tracker, inputStream, prevCommand):

    global config
    # global configFile
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

    lines = msg.split("\n")
    # extracting the command from the other peer inputStream
    fields = lines[0].split()
    command = fields[0]

    # print("fucked up prevCommand {}".format(prevCommand))
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
            transmitMessageToPeer(tracker, "ERROR\n\0")
            sys.exit(-1)
        else:
            FileList = lines[1:]
            print()
            print()
            print()
            print(" List of files available in the P2P network are")
            for line in lines[1:]:
                # print the name of the file
                print(line)
            print()
            print()
            print()
        return None, inputStream

    elif command == "AT" and prevCommand == "WHERE":
        peerIP = fields[1]
        peerPORT = int(fields[2])
        # return the Peer IP and Peer PORT tuple and inputStream as output
        return (peerIP, peerPORT), inputStream

    elif command == "OK" and prevCommand in ("LIST", "LISTENING"):
        print("LIST prev command was called")
        return None, inputStream
    elif command == "ERROR":
        sys.exit(-1)

    else:
        sys.exit(-1)


# this method is used for making socket connection with the peer
# !ERROR HERE
def InitializeConnection(address):
    IP, PORT = address
    try:
        peerConnection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except socket.error:
        sys.exit(-1)

    try:
        peerConnection.connect((IP, PORT))  # !ERROR
    except socket.error:
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
        print()
        print("Enter Path of the directory to connect to the P2P network ")
        print("<< warning :: Other peers can have access to these files>>")
        print()
        print("> ")
        sharedDir = raw_input()
        print()
        # if the path is not a dir or the path doesn't exists
        # ask again
        if not os.path.isdir(sharedDir):
            print("not a directory  : please enter valid path")
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
        fields = msg.split()
        # extract the command out of inputStream buffer string
        command = fields[0]

        # *processing request

        print("peer at {} is asking for a file".format(address))

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
                while fileREADER:
                    socketConnection.send(fileREADER)
                    fileREADER = fileSharingSEND.read(1024)
                fileSharingSEND.close()
            else:
                transmitMessageToPeer(socketConnection, "ERROR\n\0")
                socketConnection.close()
                break
        elif command == "THANKS":
            print("...File Successfully SENT....")
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
        sys.exit(-1)

    try:
        incomingSocket.bind((peerIP, peerPORT))
        print("binding the incomingSocket in incomingPeerConnection method")
    except socket.error:
        sys.exit(-1)
    # server connection for listening for incoming peer connections
    incomingSocket.listen(5)
    # incomingPeerConnectionPORT = incomingSocket.getsockname()[1]
    peerPORT = incomingSocket.getsockname()[1]
    queue.put((peerIP, peerPORT))
    peerCount = 0
    while True:
        # keep listening for incoming request
        socketConnection, address = incomingSocket.accept()
        # calling Peer method in separete thread so that main thread doesn't  have to wait for one Peer to finish
        newPeerThread = Thread(name="peer {}".format(
            peerCount), target=Peer, args=(socketConnection, address))
        # put it in background
        newPeerThread.daemon = True
        newPeerThread.start()
        # new peer is finally connected
        print("NEW PEER :::  new thread(daemon) started")
        peerCount += 1


def getFile(peer):
    print("---------------------------------")
    print("Asking for a fie from other PEER ")
    print("---------------------------------")
    global requested
    print()
    print("Requested File name : ")
    requested = raw_input()
    # ask for the file from the other peer
    transmitMessageToPeer(peer, "GIVE {}\n\0".format(requested))
    inputStream = ""
    while "\0" not in inputStream:
        inputStream += peer.recv(4096)
    index = inputStream.index("\0")
    msg = inputStream[0:index - 1]
    inputStream = inputStream[index+1:]
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
        transmitMessageToPeer(peer, "THANKS\n\0")
        peer.close()
    elif command == "ERROR":
        return
    else:
        sys.exit(-1)


def updateFilesList():
    avFile = [avfile for avfile in os.listdir(sharedDir) if os.path.isfile(
        os.path.join(sharedDir, avfile))]
    msg_list = "LIST {}\n".format(len(avFile))
    for avfile in avFile:
        msg_list += avfile + "\n"
    msg_list += "\0"
    return msg_list


'''

MAIN METHOD

'''


def main():
    global config
    global configFile
    global FileList
    global sharedDir
    configFile = "config.json"

    print()
    print(" ##################### Welcome to the SuperNOVA network ##################### ")
    print()
    if os.path.isfile(configFile):
        config = json_load(configFile)
    else:
        # else new server config file in json format
        config["trackerIP"] = "localhost"
        config["trackerPort"] = 45000
        config["peerListeningIP"] = "localhost"
        config["peerListeningPORT"] = 0
        config["sharedDIR"] = getSharedDIR()
        json_save(configFile, config)

    sharedDir = config["sharedDIR"]

    avFile = [avfile for avfile in os.listdir(
        sharedDir) if os.path.isfile(os.path.join(sharedDir, avfile))]

    # logging.debug("list of files avaialble for sharing is" + str(avFile))

    print("available files are {}".format(str(avFile)))

    trackerAdd = (config["trackerIP"], config["trackerPort"])
    # connect this peer with tracker
    print(trackerAdd)  # gives correct addresss of tracker
    tracker = InitializeConnection(trackerAdd)

    print("connection is done")
    '''

    HELLO COMMAND : #####################

    '''

    inputStream = ""
    if "user" in config:
        # if the user already in the list ( tracker list)
        transmitMessageToPeer(tracker, "HELLO " + config["user"] + "\n\0")
    else:
        # else this means this is peer's first time connecting to tracker
        transmitMessageToPeer(tracker, "HELLO\n\0")
    data, inputStream = makeConnection(tracker, inputStream, "HELLO")

    '''
    
    LISTENING FOR PEER CONNECTION COMMAND :###############
    
    '''
    peerListeningIP = config["peerListeningIP"]
    peerListeningPORT = config["peerListeningPORT"]

    queue = Queue.Queue()

    PeerconnectionListeningThread = Thread(name="PeerConnectionThread", target=incomingPeerConnections, args=(
        peerListeningIP, peerListeningPORT, queue))

    PeerconnectionListeningThread.daemon = True  # send the thread to background
    PeerconnectionListeningThread.start()

    peerListeningIP, peerListeningPORT = queue.get()
    # print(" peerListIP ==> {}".format(peerListeningIP))
    # print(" peerListPORT ==> {}".format(peerListeningPORT))

    PeerMsg = "LISTENING {} {}\n\0".format(peerListeningIP, peerListeningPORT)
    print("PeerMsg is => {}".format(PeerMsg))

    transmitMessageToPeer(tracker, PeerMsg)

    makeConnection(tracker, inputStream, "LISTENING")
    print("this peer is all setup and listening for incoming peer connections")

    '''
    
    LIST COMMAND :###############
    
    '''

    msg_list = "LIST {}\n".format(len(avFile))
    for avfile in avFile:
        msg_list += avfile + "\n"
    msg_list += "\0"
    print("list of files are..->")
    # transmitMessageToPeer(tracker, inputStream)  # ? fixed error here
    transmitMessageToPeer(tracker, msg_list)  # TODO ? FIXED ERROR HERE

    print(" break point ..................")
    print(msg_list)

    print("calling make connection with LIST")
    print("tracker is {}".format(tracker))
    # if inputStream == None:
    #     print("inputStream is None")
    # else:
    #     print("inputStream is Not None")
    makeConnection(tracker, inputStream, "LIST")
    print(" break point after makeConnetion LIST ..................")

    '''
    
    SENDLIST COMMAND :###############
    
    '''
    transmitMessageToPeer(tracker, "SENDLIST" + "\n\0")
    makeConnection(tracker, inputStream, "SENDLIST")

    # MENU
    while True:
        print()
        print("Commands Interface..")
        print()
        print()
        print("1: Request the list of peers and files available")
        print("2: Request file from a peer")
        print("3: Add New sharing Dir")
        print("4: exit the superNOVA P2P network")
        print()
        print()
        print()

        command = raw_input()

        if command == "1":
            transmitMessageToPeer(tracker, "SENDLIST " + "\n\0")
            makeConnection(tracker, inputStream, "SENDLIST")

        # TODO FIX the option 2 in  the menu

        elif command == "2":
            print("specify the peer name")

            while True:
                peerName = raw_input()
                if peerName == config["user"]:
                    print("{} try again. :: it's your username".format(peerName))
                    continue
                if peerName in [output.split()[0] for output in FileList]:
                    break
                print("{} is an invalid peer name :: TRY AGAIN".format(peerName))

            transmitMessageToPeer(tracker, "WHERE " +
                                  peerName + "\n\0")  # TODO FIXED ERROR

            (peerIP, peerPORT), inputStream = makeConnection(
                tracker, inputStream, "WHERE")

            # print("peerIP is {}".format(peerIP))
            print(
                "Initializing connection[in separate thread] with {} ".format(peerName))

            print("PeerIP ----> {}".format(peerIP))
            print("PeerPORT ----> {}".format(peerPORT))

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
