# SAIP Chaincode REST API

This is a simple REST server written in golang with endpoints for chaincode invoke and query.

  
## Usage

- Setup fabric test network and deploy the saip chaincode by [following this instructions](https://hyperledger-fabric.readthedocs.io/en/release-2.4/test_network.html).

- add this folder to fabric-samples directory
- cd into SAIP-ChaincodeRestApi directory
- Download required dependencies using `go mod download`
- Run `go run main.go` to run the REST server

## Sending Requests

Invoke endpoint accepts POST requests with chaincode function and arguments. Query endpoint accepts get requests with chainScode function and arguments.
