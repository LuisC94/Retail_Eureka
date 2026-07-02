import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { HttpClient } from '@angular/common/http';
import { environment } from 'src/environments/environment';
import { ResultModel } from 'src/app/models/result.model';
import { BasketModel } from '../shopping/models/basket.model';


const API_BASKET_URL = `${environment.apiUrl}/Basket`;

@Injectable({
    providedIn: 'root',
})
export class BasketManagementService {

    constructor(private http: HttpClient) { }

    // public methods
    allBasket(userId: number): Observable<ResultModel<BasketModel[]>> {
        return this.http.get<ResultModel<BasketModel[]>>(`${API_BASKET_URL}/BasketList/${userId}`);
    }

    save(data: BasketModel): Observable<ResultModel<BasketModel>> {
        return this.http.post<ResultModel<BasketModel>>(`${API_BASKET_URL}/Save`, data);
    }

    saveAll(data: BasketModel[]): Observable<ResultModel<BasketModel[]>> {
        return this.http.post<ResultModel<BasketModel[]>>(`${API_BASKET_URL}/SaveAll`, data);
    }

    delete(id: number, productId: number): Observable<ResultModel<BasketModel>> {
        return this.http.delete<ResultModel<BasketModel>>(`${API_BASKET_URL}/Delete/${id}/${productId}`);
    }

    deleteAll(id: number, productId: number): Observable<ResultModel<BasketModel[]>> {
        return this.http.delete<ResultModel<BasketModel[]>>(`${API_BASKET_URL}/DeleteAll/${id}/${productId}`);
    }
}
