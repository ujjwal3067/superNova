
.PHONY: default
default: clean 

#reset and clean the server logs
reset_server:
	rm -f server/configuration.json
	rm -f server/clients.json
	rm -f server/server.log

#reset and clean the clien/tpeer logs
reset_client: 
	rm -f client/configuration.json 
	rm -f client/client.log

clean : 
	find . -type f -name "*.pyc" -exec rm -vf {} \;

