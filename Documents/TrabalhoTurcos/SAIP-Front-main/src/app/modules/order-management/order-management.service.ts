import { Injectable } from '@angular/core';
import {Observable } from 'rxjs';
import { HttpClient, HttpParams } from '@angular/common/http';
import { environment } from 'src/environments/environment';
import { ResultModel } from 'src/app/models/result.model';
import { PagingResult } from 'src/app/models/paging-result.model';
import { OrderModel } from './models/order.model';
import { OrderProductModel } from './models/orderproduct.model';

const API_ORDER_URL = `${environment.apiUrl}/Order`;

@Injectable({
    providedIn: 'root',
})
export class OrderManagementService {

    constructor(private http: HttpClient) { }

    // public methods

    paging(pageNumber: number, pageSize: number, userId?: number, filterText?: string): Observable<ResultModel<PagingResult<OrderModel[]>>> {
        return this.http.get<ResultModel<PagingResult<OrderModel[]>>>(`${API_ORDER_URL}/Paginate/${userId}`, 
            { params: new HttpParams().set("PageNumber", pageNumber).set("PageSize", pageSize).set("FilterText", filterText!==undefined ? filterText : '') });
    }

    save(data: OrderModel): Observable<ResultModel<OrderModel>> {
        return this.http.post<ResultModel<OrderModel>>(`${API_ORDER_URL}/Save`, data);
    }

    getById(id: number): Observable<ResultModel<OrderModel>> {
        return this.http.get<ResultModel<OrderModel>>(`${API_ORDER_URL}/${id}`);
    }

    comingPaging(pageNumber: number, pageSize: number, userId?: number): Observable<ResultModel<PagingResult<OrderProductModel[]>>> {
        return this.http.get<ResultModel<PagingResult<OrderProductModel[]>>>(`${API_ORDER_URL}/Paginate/${userId}`, 
            { params: new HttpParams().set("PageNumber", pageNumber).set("PageSize", pageSize) });
    }
}
