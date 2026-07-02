# SAIP Chaincode

## Usage (For Linux)

- Depending on your operating system, you can install hyperledger-fabric from here (https://hyperledger-fabric.readthedocs.io/en/release-2.4/prereqs.html and https://hyperledger-fabric.readthedocs.io/en/release-2.4/install.html).

- add this folder and SAIP-ChaincodeRestApi folder to fabric-samples directory

- Start the network by followibg commands

    cd fabric-samples/test-network

    ./network.sh down

    ./network.sh up createChannel (if 'jq' errors sudo apt-get update && sudo apt-get install jq)

- Package the smart contract

    cd fabric-samples/SAIP-Chaincode

    npm install

    cd fabric-samples/test-network

    export PATH=${PWD}/../bin:$PATH

    export FABRIC_CFG_PATH=$PWD/../config/

    peer version

    peer lifecycle chaincode package saip.tar.gz --path ../SAIP-Chaincode/ --lang golang --label saip_1.0

- Install the chaincode package

    export CORE_PEER_TLS_ENABLED=true

    export CORE_PEER_LOCALMSPID="Org1MSP"

    export CORE_PEER_TLS_ROOTCERT_FILE=${PWD}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt

    export CORE_PEER_MSPCONFIGPATH=${PWD}/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp

    export CORE_PEER_ADDRESS=localhost:7051

    peer lifecycle chaincode install saip.tar.gz

    export CORE_PEER_LOCALMSPID="Org2MSP"

    export CORE_PEER_TLS_ROOTCERT_FILE=${PWD}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt

    export CORE_PEER_MSPCONFIGPATH=${PWD}/organizations/peerOrganizations/org2.example.com/users/Admin@org2.example.com/msp

    export CORE_PEER_ADDRESS=localhost:9051
    
    peer lifecycle chaincode install saip.tar.gz

- Approve a chaincode definition

    peer lifecycle chaincode queryinstalled (copy packageId from response)

    export CC_PACKAGE_ID=paste packageId

    peer lifecycle chaincode approveformyorg -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com --channelID mychannel --name saip --version 1.0 --package-id $CC_PACKAGE_ID --sequence 1 --tls --cafile "${PWD}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem"

    export CORE_PEER_LOCALMSPID="Org1MSP"

    export CORE_PEER_MSPCONFIGPATH=${PWD}/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp

    export CORE_PEER_TLS_ROOTCERT_FILE=${PWD}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt

    export CORE_PEER_ADDRESS=localhost:7051

    peer lifecycle chaincode approveformyorg -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com --channelID mychannel --name saip --version 1.0 --package-id $CC_PACKAGE_ID --sequence 1 --tls --cafile "${PWD}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem"

- Committing the chaincode definition to the channel

    peer lifecycle chaincode checkcommitreadiness --channelID mychannel --name saip --version 1.0 --sequence 1 --tls --cafile "${PWD}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem" --output json

    peer lifecycle chaincode commit -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com --channelID mychannel --name saip --version 1.0 --sequence 1 --tls --cafile "${PWD}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem" --peerAddresses localhost:7051 --tlsRootCertFiles "${PWD}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt" --peerAddresses localhost:9051 --tlsRootCertFiles "${PWD}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt"

    peer lifecycle chaincode querycommitted --channelID mychannel --name saip --cafile "${PWD}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem"

- Invoking the chaincode

    peer chaincode invoke -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com --tls --cafile "${PWD}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem" -C mychannel -n saip --peerAddresses localhost:7051 --tlsRootCertFiles "${PWD}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt" --peerAddresses localhost:9051 --tlsRootCertFiles "${PWD}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt" -c '{"function":"InitLedger","Args":[]}'

    Chaincode deploying and invoking successfully.

- Running rest api for chaincode

    To access the chaincode from outside, you must start the SAIP-ChaincodeRestApi (You can find instructions on how to start it in the readme file located in the SAIP-ChaincodeRestApi folder.).



