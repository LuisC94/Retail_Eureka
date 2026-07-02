import { Injectable } from "@angular/core";
import { BehaviorSubject } from "rxjs";

@Injectable({
    providedIn: 'root',
})
export class AlertService {

    private _alert$? = new BehaviorSubject<any>(undefined);
    public alert$ = this._alert$?.asObservable();

    constructor() { 
    }

    clearAlert() {
        this._alert$?.next(undefined);
    }

    createAlert(type: string, message: string) {
        this._alert$?.next({type: type, message: message});    
    }

    getAlert() {
        return this._alert$?.value;
    }
}