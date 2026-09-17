package web

import (
	"fmt"
	"net/http"

	"google.golang.org/grpc/status"
)

// Invoke handles chaincode invoke requests.
func (setup *OrgSetup) Invoke(w http.ResponseWriter, r *http.Request) {
	fmt.Println("Received Invoke request")
	if err := r.ParseForm(); err != nil {
		fmt.Fprintf(w, "ParseForm() err: %s", err)
		return
	}
	chainCodeName := r.FormValue("chaincodeid")
	channelID := r.FormValue("channelid")
	function := r.FormValue("function")
	args := r.Form["args"]
	fmt.Printf("channel: %s, chaincode: %s, function: %s, args: %s\n", channelID, chainCodeName, function, args)

	network := setup.Gateway.GetNetwork(channelID)
	contract := network.GetContract(chainCodeName)

	submitResult, err := contract.SubmitTransaction(function, args...)
	if err != nil {
		detailMsg := ""
		if grpcStatus, ok := status.FromError(err); ok {
			detailMsg = fmt.Sprintf(" [Code: %s, Message: %s]", grpcStatus.Code(), grpcStatus.Message())
			for _, detail := range grpcStatus.Details() {
				detailMsg += fmt.Sprintf(" [Detail: %v]", detail)
			}
		}

		fmt.Printf("Error submitting transaction: %s%s\n", err, detailMsg)
		fmt.Fprintf(w, "Error submitting transaction: %s%s", err, detailMsg)
		return
	}

	fmt.Fprintf(w, "Response: %s", string(submitResult))
}
