import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { HttpClient, HttpParams } from '@angular/common/http';
import { environment } from 'src/environments/environment';
import { ResultModel } from 'src/app/models/result.model';
import { PagingResult } from 'src/app/models/paging-result.model';
import { OrderProductModel } from './models/orderproduct.model';
import { FileModel } from 'src/app/models/file.model';

const API_ORDER_URL = `${environment.apiUrl}/Order`;
const API_FILE_URL = `${environment.apiUrl}/File`;

@Injectable({
    providedIn: 'root',
})
export class ComingOrderManagementService {

    constructor(private http: HttpClient) { }

    // public methods

    paging(pageNumber: number, pageSize: number, userId?: number, filterText?: string): Observable<ResultModel<PagingResult<OrderProductModel[]>>> {
        return this.http.get<ResultModel<PagingResult<OrderProductModel[]>>>(`${API_ORDER_URL}/ComingPaginate/${userId}`, 
            { params: new HttpParams().set("PageNumber", pageNumber).set("PageSize", pageSize).set("FilterText", filterText!==undefined ? filterText : '') });
    }

    getById(id: number): Observable<ResultModel<OrderProductModel>> {
        return this.http.get<ResultModel<OrderProductModel>>(`${API_ORDER_URL}/ComingOrder/${id}`);
    }

    updateStatus(orderProduct: OrderProductModel): Observable<ResultModel<OrderProductModel>> {
        return this.http.post<ResultModel<OrderProductModel>>(`${API_ORDER_URL}/UpdateStatus`, orderProduct);
    }

    upload(data: FormData): Observable<ResultModel<FileModel>> {
        return this.http.post<ResultModel<FileModel>>(`${API_FILE_URL}/Save`, data);
    }

    addInvoice(data: OrderProductModel): Observable<ResultModel<OrderProductModel>> {
        return this.http.post<ResultModel<OrderProductModel>>(`${API_ORDER_URL}/AddInvoice`, data);
    }

    deleteInvoice(orderProductId: number): Observable<ResultModel<OrderProductModel>> {
        return this.http.delete<ResultModel<OrderProductModel>>(`${API_ORDER_URL}/DeleteInvoice/${orderProductId}`);
    }
}
