package web

import (
	"fmt"
	"net/http"
)

// Query handles chaincode query requests (supports both GET and POST).
func (setup OrgSetup) Query(w http.ResponseWriter, r *http.Request) {
	fmt.Println("Received Query request")
	if err := r.ParseForm(); err != nil {
		fmt.Fprintf(w, "ParseForm() err: %s", err)
		return
	}
	chainCodeName := r.FormValue("chaincodeid")
	channelID := r.FormValue("channelid")
	function := r.FormValue("function")
	args := r.Form["args"]
	callerID := r.FormValue("callerid")
	if callerID != "" {
		if function == "ReadOrder" && len(args) == 1 {
			args = append(args, callerID)
		} else if function == "GetAllOrders" && len(args) == 0 {
			args = append(args, callerID)
		}
	}
	fmt.Printf("channel: %s, chaincode: %s, function: %s, args: %s, callerid: %s\n", channelID, chainCodeName, function, args, callerID)
	network := setup.Gateway.GetNetwork(channelID)
	contract := network.GetContract(chainCodeName)
	evaluateResponse, err := contract.EvaluateTransaction(function, args...)
	if err != nil {
		fmt.Fprintf(w, "Error: %s", err)
		return
	}
	fmt.Fprintf(w, "Response: %s", evaluateResponse)
}
