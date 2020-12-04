#makefile 
#author Ujjwal kumar ID : 260730680

.PHONY: default
default: clean 

#reset and clean the server logs
reset_server:
	rm -f Tracker/configuration.json
	rm -f Tracker/clients.json
	rm -f Tracker/server.log

#reset and clean the clien/tpeer logs
reset_client: 
	rm -f Peer/configuration.json 
	rm -f Peer/client.log

clean : 
	find . -type f -name "*.pyc" -exec rm -vf {} \;

