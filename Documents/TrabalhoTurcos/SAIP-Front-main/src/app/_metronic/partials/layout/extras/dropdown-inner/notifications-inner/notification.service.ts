import { HttpClient } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { BehaviorSubject, Observable } from "rxjs";
import { NotificationModel } from "src/app/models/notification.model";
import { ResultModel } from "src/app/models/result.model";
import { environment } from "src/environments/environment";
import { webSocket } from 'rxjs/webSocket';

const API_NOTIFICATION_URL = `${environment.apiUrl}/Notification`;

@Injectable({
    providedIn: 'root',
})
export class NotificationService {

    private _notifications$ = new BehaviorSubject<NotificationModel[] | undefined>(undefined)
    public notifications$ = this._notifications$.asObservable()

    constructor(private http: HttpClient) { 
    }

    updateNotifications(userId: number) {
        this.all(userId).subscribe(result => {
            this._notifications$.next(undefined);

            if(result.isSuccess) {
                this._notifications$.next(result.data);
            }
        })
    }

    all(userId: number): Observable<ResultModel<NotificationModel[]>> {
        return this.http.get<ResultModel<NotificationModel[]>>(`${API_NOTIFICATION_URL}/All/${userId}`);
    }

    read(id: number): Observable<ResultModel<NotificationModel>> {
        return this.http.get<ResultModel<NotificationModel>>(`${API_NOTIFICATION_URL}/Read/${id}`);
    }

    delete(id: number): Observable<ResultModel<NotificationModel>> {
        return this.http.delete<ResultModel<NotificationModel>>(`${API_NOTIFICATION_URL}/Delete/${id}`);
    }
}