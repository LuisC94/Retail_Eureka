import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { HttpClient, HttpParams } from '@angular/common/http';
import { environment } from 'src/environments/environment';
import { ResultModel } from 'src/app/models/result.model';
import { PagingResult } from 'src/app/models/paging-result.model';
import { ProductModel } from './models/product.model';

const API_SHOPPING_URL = `${environment.apiUrl}/Product`;

@Injectable({
    providedIn: 'root',
})
export class ShoppingService {

    constructor(private http: HttpClient) { }

    // public methods
    paging(pageNumber: number, pageSize: number, categoryId: number, userId: number, filterText?: string): Observable<ResultModel<PagingResult<ProductModel[]>>> {
        return this.http.get<ResultModel<PagingResult<ProductModel[]>>>(`${API_SHOPPING_URL}/ShoppingPaginate/${categoryId}/${userId}`, 
            { params: new HttpParams().set("PageNumber", pageNumber).set("PageSize", pageSize).set("FilterText", filterText!==undefined ? filterText : '') });
    }
}
