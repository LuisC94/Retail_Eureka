import { Injectable } from "@angular/core";
import { webSocket, WebSocketSubject } from "rxjs/webSocket";
import { AlertService } from "src/app/_metronic/partials/layout/alert/alert.service";
import { NotificationService } from "src/app/_metronic/partials/layout/extras/dropdown-inner/notifications-inner/notification.service";
import { environment } from "src/environments/environment";

@Injectable({
    providedIn: 'root',
})
export class WebSocketService {

    socket: WebSocketSubject<any>;

    constructor(
        private notificationService: NotificationService,
        private alertService: AlertService
    ) { }

    connectToWebSocket(userId: number) {
        this.socket
        .subscribe({
            next: message => { 
                this.alertService.createAlert("warning", message);
                setTimeout(() => {
                    this.notificationService.updateNotifications(userId);
                }, 500)            
            },
            error: err => { 
                console.log("Web socket errors :" + err)
            },
            complete: () => { 
                console.log("Web socket disconnected")
            }
        });
    }

    openWebSocket(userId: number) {
        this.socket = webSocket({
            url: `${environment.wsUrl}?userId=${userId}`,
            deserializer: msg => msg.data

        });        
        
        this.connectToWebSocket(userId); 
    }

    closeWebSocket() {
        if(this.socket) {
            this.socket.complete();
        }
    }
}