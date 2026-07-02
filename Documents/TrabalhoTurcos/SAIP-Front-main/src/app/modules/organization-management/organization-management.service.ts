import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { HttpClient, HttpParams } from '@angular/common/http';
import { environment } from 'src/environments/environment';
import { ResultModel } from 'src/app/models/result.model';
import { PagingResult } from 'src/app/models/paging-result.model';
import { OrganizationModel } from './models/organization.model';

const API_ORGANIZATION_URL = `${environment.apiUrl}/Organization`;

@Injectable({
    providedIn: 'root',
})
export class OrganizationManagementService {

    constructor(private http: HttpClient) { }

    // public methods

    paging(pageNumber: number, pageSize: number, filterText?: string): Observable<ResultModel<PagingResult<OrganizationModel[]>>> {
        return this.http.get<ResultModel<PagingResult<OrganizationModel[]>>>(`${API_ORGANIZATION_URL}/Paginate`, 
            { params: new HttpParams().set("PageNumber", pageNumber).set("PageSize", pageSize).set("FilterText", filterText!==undefined ? filterText : '') });
    }

    all(): Observable<ResultModel<OrganizationModel[]>> {
        return this.http.get<ResultModel<OrganizationModel[]>>(`${API_ORGANIZATION_URL}/All`);
    }

    getById(id: number): Observable<ResultModel<OrganizationModel>> {
        return this.http.get<ResultModel<OrganizationModel>>(`${API_ORGANIZATION_URL}/${id}`);
    }

    save(data: OrganizationModel): Observable<ResultModel<OrganizationModel>> {
        return this.http.post<ResultModel<OrganizationModel>>(`${API_ORGANIZATION_URL}/Save`, data);
    }

    edit(data: OrganizationModel): Observable<ResultModel<OrganizationModel>> {
        return this.http.post<ResultModel<OrganizationModel>>(`${API_ORGANIZATION_URL}/Update`, data);
    }

    delete(id: number): Observable<ResultModel<OrganizationModel[]>> {
        return this.http.delete<ResultModel<OrganizationModel[]>>(`${API_ORGANIZATION_URL}/Delete/${id}`);
    }
}
