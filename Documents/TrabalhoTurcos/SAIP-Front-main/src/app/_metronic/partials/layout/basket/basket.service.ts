import { HttpClient } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { BehaviorSubject, Observable, Subject } from "rxjs";
import { ResultModel } from "src/app/models/result.model";
import { AuthService } from "src/app/modules/auth";
import { BasketModel } from "src/app/modules/shopping/models/basket.model";
import { environment } from "src/environments/environment";

const API_ORDER_URL = `${environment.apiUrl}/Basket`;

@Injectable({
    providedIn: 'root',
  })
  export class BasketService {
    private _basket$ = new BehaviorSubject<BasketModel[]>([])
    public basket$ = this._basket$.asObservable()

    private _localStorage: Storage;

    constructor(private http: HttpClient, private authService: AuthService) {
        this._localStorage = localStorage;
     }

    allBasket(userId: number): Observable<ResultModel<BasketModel[]>> {
        return this.http.get<ResultModel<BasketModel[]>>(`${API_ORDER_URL}/BasketList/${userId}`);
    }
    
    loadBasketFromDb() {
        var currentUser = this.authService.currentUserValue;

        if(currentUser) {
            this.allBasket(currentUser.id).subscribe(result => { 
                if(result.data) {
                    result.data.forEach(item => {
                        var product = item.product!;
                        product.fileResult.fileContents = "data:" + product.fileResult.contentType + ";base64," + product.fileResult.fileContents;
                        item.product = product;
                    })
                    this._basket$.next(result.data)
                }
                else{
                    this._basket$.next([])
                }
            });
        }
    }

    setBasket(data: BasketModel[]) {
        this._basket$.next([])

        const jsonData = JSON.stringify(data)
        this._localStorage.setItem('basket', jsonData)
        this._basket$.next(data)
    }

    loadBasket() {
        const data = JSON.parse(this._localStorage.getItem('basket') as string) as BasketModel[];
        this._basket$.next(data)
    }
    
    getBasket() {
        return this._basket$.value;
    }
}