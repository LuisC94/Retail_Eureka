package main

import (
	"fmt"
	"log"
	"path/filepath"
	"rest-api-go/web"
)

func main() {
	//Initialize setup for Org1
	cryptoPath := "../fabric-samples/test-network/organizations/peerOrganizations/org1.example.com"
	
	// Dynamic Certificate Finding
	certDir := cryptoPath + "/users/User1@org1.example.com/msp/signcerts/"
	files, err := filepath.Glob(certDir + "*cert.pem")
	if err != nil || len(files) == 0 {
		log.Fatalf("Error finding certificate file in %s: %v", certDir, err)
	}
	certPath := files[0] // Use the first matching file
	fmt.Printf("Using certificate: %s\n", certPath)

	// Dynamic Key Finding
	keyDir := cryptoPath + "/users/User1@org1.example.com/msp/keystore/"
	keyFiles, err := filepath.Glob(keyDir + "*_sk")
	if err != nil || len(keyFiles) == 0 {
		log.Fatalf("Error finding private key file in %s: %v", keyDir, err)
	}
	keyPath := keyFiles[0]
	fmt.Printf("Using private key: %s\n", keyPath)

	orgConfig := web.OrgSetup{
		OrgName:      "Org1",
		MSPID:        "Org1MSP",
		CertPath:     certPath,
		KeyPath:      keyPath,
		TLSCertPath:  cryptoPath + "/peers/peer0.org1.example.com/tls/ca.crt",
		PeerEndpoint: "dns:///localhost:7051",
		GatewayPeer:  "peer0.org1.example.com",
	}

	orgSetup, err := web.Initialize(orgConfig)
	if err != nil {
		fmt.Println("Error initializing setup for Org1: ", err)
	}
	web.Serve(web.OrgSetup(*orgSetup))
}
