#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
from library.library import send_message


DEBUG = False


CONFIG_FILE = ""
CONFIG = {}
SHARED_DIR = ""
listFIlES = []
FILERequested = ""


# ASYNC CALL
signal.signal(signal.SIGINT, sigint_handler)


# keep checking for connection
def makeCONNECTION(TRACKER, BUFFER, prevCmd):

    global CONFIG
    global listFIlES
    global FILERequested

    # parse message
    if "\0" not in BUFFER:
        BUFFER += TRACKER.recv(4096)
        return makeCONNECTION(TRACKER, BUFFER, prevCmd)
    else:
        index = BUFFER.index("\0")
        message = BUFFER[0:index-1]
        BUFFER = BUFFER[index+1:]

    logging.info("message received: " + message)

    lines = message.split("\n")
    fields = lines[0].split()
    command = fields[0]

    # protocol messages and answers
    if command == "AVAILABLE":
        username = fields[1]
        username = get_name(username)

        send_message(TRACKER, "IWANT " + username + "\n\0")

        return makeCONNECTION(TRACKER, BUFFER, "IWANT")

    elif command == "WELCOME":
        username = fields[1]
        CONFIG["username"] = username
        json_save(CONFIG_FILE, CONFIG)

        return None, BUFFER

    elif command == "FULLLIST" and prevCmd == "SENDLIST":
        number_of_files = int(fields[1])

        if number_of_files != (len(lines) - 1):
            logging.warning("invalid FULLLIST message, wrong number of files")
            send_message(TRACKER, "ERROR\n\0")
            sys.exit(-1)
        else:
            listFIlES = lines[1:]

            # cli_output
            print()
            print("full list of clients' files")
            for line in lines[1:]:
                print(line)

        return None, BUFFER

    elif command == "AT" and prevCmd == "WHERE":
        peer_ip = fields[1]
        peer_port = int(fields[2])

        return (peer_ip, peer_port), BUFFER

    elif command == "OK" and prevCmd in ("LIST", "LISTENING"):
        return None, BUFFER

    elif command == "ERROR":
        logging.warning("ERROR message received, exiting")
        sys.exit(-1)

    else:
        # TODO
        # handle invalid commands
        logging.warning(
            'an invalid command was received: "{}"'.format(command))
        sys.exit(-1)


def connection_init(address):
    """
    create a socket and establish a connection
    """

    ip, port = address

    try:
        connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except socket.error:
        logging.error("socket.socket error")
        sys.exit(-1)

    try:
        connection.connect((ip, port))
        # cli_output
        logging.info("connected to TRACKER or peer {}:{}".format(ip, port))
    except socket.error:
        # cli_output
        logging.info("failed to connect to port {}, exiting".format(port))
        sys.exit(-1)

    return connection


def get_name(username_):
    """
    get a username from the user
    """

    # cli_output
    print('Specify a username (press enter for the default "{}"): '.format(username_))
    username = raw_input()

    if username == "":
        username = username_

    return username


def get_sharing_directory():
    """
    get the sharing directory from the user
    """

    SHARED_DIR = ""

    while not os.path.isdir(SHARED_DIR):
        # cli_output
        print()
        print("Enter the directory to share:")
        SHARED_DIR = raw_input()

        if not os.path.isdir(SHARED_DIR):
            print(""""{}" doesn't seem like a valid directory, try again""".format(
                SHARED_DIR))

    return SHARED_DIR


def peer_function(connection, address):
    """
    connect to a peer

    connection : connection socket
    address : (IP_address, port)
    """
    global SHARED_DIR

    BUFFER = ""

    while True:
        # parse message
        while "\0" not in BUFFER:
            BUFFER += connection.recv(4096)

        index = BUFFER.index("\0")
        message = BUFFER[0:index-1]
        BUFFER = BUFFER[index+1:]

        logging.info("message received: " + message)

        fields = message.split()
        command = fields[0]
        # handle and respond to the message
        if command == "GIVE":
            file_ = SHARED_DIR + "/" + fields[1]

            if os.path.isfile(file_):
                # get the file size
                file_size = os.path.getsize(file_)

                send_message(connection, "TAKE {}\n\0".format(str(file_size)))

                file__ = open(file_, "rb")

                file_buffer = ""
                file_buffer = file__.read(1024)
                while file_buffer:
                    print("sending: " + file_buffer)
                    connection.send(file_buffer)
                    file_buffer = file__.read(1024)

                # cli_output
                logging.info("file {} sent".format(file_))

                file__.close()
            else:
                send_message(connection, "ERROR\n\0")
                connection.close()
                break

        elif command == "THANKS":
            connection.close()
            break

        else:
            send_message(connection, "ERROR\n\0")
            connection.close()
            break

    return


def listen(listening_ip, listening_port, queue):
    """
    create a TRACKER socket and start listening for incoming connections
    """

    try:
        listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except socket.error:
        logging.error("socket.socket error")
        sys.exit(-1)

    try:
        listening_socket.bind((listening_ip, listening_port))
    except socket.error:
        logging.error("port {} in use, exiting".format(listening_port))
        sys.exit(-1)

    # listen for incoming connections
    listening_socket.listen(5)

    # cli_output
    logging.info("client listening on {}:{}".format(
        listening_ip, str(listening_port)))

    listening_port = listening_socket.getsockname()[1]

    # pass the listening_ip and listening_port to the main thread
    queue.put((listening_ip, listening_port))

    # handle incoming peer connections
    peer_counter = 0
    while True:
        connection, address = listening_socket.accept()
        # cli_output
        logging.info("a peer connected from {}:{}".format(
            address[0], str(address[1])))

        peer_thread = Thread(name="peer {}".format(peer_counter),
                             target=peer_function, args=(connection, address))
        # TODO
        # handle differently, terminate gracefully
        peer_thread.daemon = True
        peer_thread.start()

        peer_counter += 1


def give_me(peer):
    """
    handle file requests and transfers
    """

    global FILERequested

    # cli_output
    print()
    print("file name:")
    FILERequested = raw_input()

    send_message(peer, "GIVE {}\n\0".format(FILERequested))

    BUFFER = ""

    # parse message
    while "\0" not in BUFFER:
        BUFFER += peer.recv(4096)

    index = BUFFER.index("\0")
    message = BUFFER[0:index-1]
    BUFFER = BUFFER[index+1:]

    logging.info("message received: " + message)

    fields = message.split()
    command = fields[0]

    if command == "TAKE":
        file_size = fields[1]

        # get the file
        while len(BUFFER) < int(file_size):
            BUFFER += peer.recv(4096)
            logging.debug("received: " + BUFFER)
            # TODO
            # save the file chunk by chunk

        file_to_save = open(SHARED_DIR + "/" + FILERequested, "wb")
        file_to_save.write(BUFFER)
        file_to_save.close()

        logging.info("file {} received".format(FILERequested))
        logging.info(
            "reconnect to the TRACKER to refresh the shared files list")
        send_message(peer, "THANKS\n\0")
        peer.close()

    elif command == "ERROR":
        return

    else:
        # TODO
        # handle invalid commands
        logging.warning(
            'an invalid command was received: "{}"'.format(command))
        sys.exit(-1)


def main():
    global CONFIG
    global CONFIG_FILE
    global listFIlES
    global SHARED_DIR

    # logging CONFIG
    logging.basicConfig(level=logging.DEBUG,
                        format="[%(levelname)s] (%(threadName)s) %(message)s",
                        filename="client.log",
                        filemode="w")
    console = logging.StreamHandler()
    if DEBUG:
        # set the console logging level to debug
        console.setLevel(logging.DEBUG)
    else:
        # set the console logging level to info
        console.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "[%(levelname)s] (%(threadName)s) %(message)s")
    console.setFormatter(formatter)
    logging.getLogger("").addHandler(console)

    CONFIG_FILE = "CONFIG.json"

    if os.path.isfile(CONFIG_FILE):
        # load the configuration from the json file
        CONFIG = json_load(CONFIG_FILE)
    else:
        # create and initialize the configuration file
        CONFIG["server_host"] = "localhost"
        CONFIG["server_port"] = 45000
        CONFIG["listening_ip"] = "localhost"
        CONFIG["listening_port"] = 0

        CONFIG["SHARED_DIR"] = get_sharing_directory()

        json_save(CONFIG_FILE, CONFIG)

    logging.debug("CONFIG: " + str(CONFIG))

    SHARED_DIR = CONFIG["SHARED_DIR"]
    files_list = [file_ for file_ in os.listdir(
        SHARED_DIR) if os.path.isfile(os.path.join(SHARED_DIR, file_))]

    logging.debug("files_list: " + str(files_list))

    server_address = (CONFIG["server_host"],
                      CONFIG["server_port"])
    TRACKER = connection_init(server_address)

    # start with an empty incoming message buffer
    BUFFER = ""

    # send HELLO command
    ############################################################################
    if "username" in CONFIG:
        send_message(TRACKER, "HELLO " + CONFIG["username"] + "\n\0")
    else:
        send_message(TRACKER, "HELLO\n\0")

    unneeded, BUFFER = makeCONNECTION(TRACKER, BUFFER, "HELLO")

    # send LISTENING command
    ############################################################################
    listening_ip = CONFIG["listening_ip"]
    listening_port = CONFIG["listening_port"]

    queue = Queue.Queue()

    # spawn listening thread
    listening_thread = Thread(name="ListeningThread", target=listen,
                              args=(listening_ip, listening_port, queue))
    # TODO
    # handle differently, terminate gracefully
    listening_thread.daemon = True
    listening_thread.start()

    listening_ip, listening_port = queue.get()

    listening_message = "LISTENING {} {}\n\0".format(
        listening_ip, listening_port)
    send_message(TRACKER, listening_message)

    makeCONNECTION(TRACKER, BUFFER, "LISTENING")

    # send LIST command
    ############################################################################
    list_message = "LIST {}\n".format(len(files_list))
    for file_ in files_list:
        list_message += file_ + "\n"
    list_message += "\0"
    send_message(TRACKER, list_message)

    makeCONNECTION(TRACKER, BUFFER, "LIST")

    # send SENDLIST command
    ############################################################################
    send_message(TRACKER, "SENDLIST " + "\n\0")

    makeCONNECTION(TRACKER, BUFFER, "SENDLIST")

    # options menu/loop
    ############################################################################
    while True:
        print()
        print("options:")
        print("1: SENDLIST : request the list of clients and shared files")
        print("2: WHERE : request the IP address and port of the specified client")
        print("4: SHARE : specify the sharing directory")
        print("5: QUIT : exit the program")

        option = raw_input()
        if option in ["1", "sendlist", "SENDLIST"]:
            send_message(TRACKER, "SENDLIST " + "\n\0")

            makeCONNECTION(TRACKER, BUFFER, "SENDLIST")

        elif option in ["2", "where", "WHERE"]:
            print("Enter the username of the client:")

            while True:
                client = raw_input()

                if client == CONFIG["username"]:
                    print("{} is you, try again: ".format(client))
                    continue

                if client in [pair.split()[0] for pair in listFIlES]:
                    break

                print("{} is an invalid client username, try again: ".format(client))

            send_message(TRACKER, "WHERE " + client + "\n\0")

            (peer_ip, peer_port), BUFFER = makeCONNECTION(
                TRACKER, BUFFER, "WHERE")

            peer = connection_init((peer_ip, peer_port))

            give_me(peer)

        elif option in ["4", "share", "SHARE"]:
            CONFIG["SHARED_DIR"] = get_sharing_directory()
            json_save(CONFIG_FILE, CONFIG)

        elif option in ["5", "quit", "QUIT"]:
            sys.exit(0)

        else:
            print("invalid option, try again")


if __name__ == "__main__":
    main()
