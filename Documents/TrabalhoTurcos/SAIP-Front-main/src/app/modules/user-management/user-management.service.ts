import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { HttpClient, HttpParams } from '@angular/common/http';
import { environment } from 'src/environments/environment';
import { ResultModel } from 'src/app/models/result.model';
import { PagingResult } from 'src/app/models/paging-result.model';
import { PermissionModel } from './models/permission.model';
import { RoleModel } from './models/role.model';
import { UserModel } from './models/user.model';
import { FileModel } from 'src/app/models/file.model';
import { UserAddressModel } from './models/user-address.model';

const API_USER_PERMISSION_URL = `${environment.apiUrl}/Permission`;
const API_USER_ROLE_URL = `${environment.apiUrl}/Role`;
const API_USER_URL = `${environment.apiUrl}/User`;
const API_FILE_URL = `${environment.apiUrl}/File`;

@Injectable({
    providedIn: 'root',
})
export class UserManagementService {

    private _user$ = new BehaviorSubject<UserModel | undefined>(undefined);
    public user$ = this._user$.asObservable();

    constructor(private http: HttpClient) { }

    updateUser(userId: number) {
        if (userId) {
            this.getUserById(userId).subscribe(result => {
                this._user$.next(undefined);

                if (result.isSuccess) {
                    if (result.data.fileId) {
                        result.data.fileResult.fileContents = "data:" + result.data.fileResult.contentType + ";base64," + result.data.fileResult.fileContents;
                    }

                    this._user$.next(result.data);
                }
            })
        }
        else {
            this._user$.next(undefined);
        }
    }

    getUser() {
        return this._user$.value;
    }

    // public methods
    permissionPaging(pageNumber: number, pageSize: number, filterText?: string): Observable<ResultModel<PagingResult<PermissionModel[]>>> {
        return this.http.get<ResultModel<PagingResult<PermissionModel[]>>>(`${API_USER_PERMISSION_URL}/Paginate`,
            { params: new HttpParams().set("PageNumber", pageNumber).set("PageSize", pageSize).set("FilterText", filterText !== undefined ? filterText : '') });
    }

    allPermissions(): Observable<ResultModel<PermissionModel[]>> {
        return this.http.get<ResultModel<PermissionModel[]>>(`${API_USER_PERMISSION_URL}/All`);
    }

    getPermissionById(id: number): Observable<ResultModel<PermissionModel>> {
        return this.http.get<ResultModel<PermissionModel>>(`${API_USER_PERMISSION_URL}/${id}`);
    }

    permissionSave(data: PermissionModel): Observable<ResultModel<PermissionModel>> {
        return this.http.post<ResultModel<PermissionModel>>(`${API_USER_PERMISSION_URL}/Save`, data);
    }

    permissionEdit(data: PermissionModel): Observable<ResultModel<PermissionModel>> {
        return this.http.post<ResultModel<PermissionModel>>(`${API_USER_PERMISSION_URL}/Update`, data);
    }

    permissionDelete(id: number): Observable<ResultModel<PermissionModel[]>> {
        return this.http.delete<ResultModel<PermissionModel[]>>(`${API_USER_PERMISSION_URL}/Delete/${id}`);
    }

    rolePaging(pageNumber: number, pageSize: number, filterText?: string): Observable<ResultModel<PagingResult<RoleModel[]>>> {
        return this.http.get<ResultModel<PagingResult<RoleModel[]>>>(`${API_USER_ROLE_URL}/Paginate`,
            { params: new HttpParams().set("PageNumber", pageNumber).set("PageSize", pageSize).set("FilterText", filterText !== undefined ? filterText : '') });
    }

    allRoles(): Observable<ResultModel<RoleModel[]>> {
        return this.http.get<ResultModel<RoleModel[]>>(`${API_USER_ROLE_URL}/All`);
    }

    getRoleById(id: number): Observable<ResultModel<RoleModel>> {
        return this.http.get<ResultModel<RoleModel>>(`${API_USER_ROLE_URL}/${id}`);
    }

    roleSave(data: RoleModel): Observable<ResultModel<RoleModel>> {
        return this.http.post<ResultModel<RoleModel>>(`${API_USER_ROLE_URL}/Save`, data);
    }

    roleEdit(data: RoleModel): Observable<ResultModel<RoleModel>> {
        return this.http.post<ResultModel<RoleModel>>(`${API_USER_ROLE_URL}/Update`, data);
    }

    roleDelete(id: number): Observable<ResultModel<RoleModel[]>> {
        return this.http.delete<ResultModel<RoleModel[]>>(`${API_USER_ROLE_URL}/Delete/${id}`);
    }

    userPaging(pageNumber: number, pageSize: number, filterText?: string): Observable<ResultModel<PagingResult<UserModel[]>>> {
        return this.http.get<ResultModel<PagingResult<UserModel[]>>>(`${API_USER_URL}/Paginate`,
            { params: new HttpParams().set("PageNumber", pageNumber).set("PageSize", pageSize).set("FilterText", filterText !== undefined ? filterText : '') });
    }

    allUsers(): Observable<ResultModel<UserModel[]>> {
        return this.http.get<ResultModel<UserModel[]>>(`${API_USER_URL}/All`);
    }

    getUserById(id: number): Observable<ResultModel<UserModel>> {
        return this.http.get<ResultModel<UserModel>>(`${API_USER_URL}/${id}`);
    }

    userSave(data: UserModel): Observable<ResultModel<UserModel>> {
        return this.http.post<ResultModel<UserModel>>(`${API_USER_URL}/Save`, data);
    }

    userEdit(data: UserModel): Observable<ResultModel<UserModel>> {
        return this.http.post<ResultModel<UserModel>>(`${API_USER_URL}/Update`, data);
    }

    userProfileEdit(data: UserModel): Observable<ResultModel<UserModel>> {
        return this.http.post<ResultModel<UserModel>>(`${API_USER_URL}/UserProfileEdit`, data);
    }

    userDelete(id: number): Observable<ResultModel<UserModel[]>> {
        return this.http.delete<ResultModel<UserModel[]>>(`${API_USER_URL}/Delete/${id}`);
    }

    upload(data: FormData): Observable<ResultModel<FileModel>> {
        return this.http.post<ResultModel<FileModel>>(`${API_FILE_URL}/Save`, data);
    }

    userAvatarEdit(id: number, fileId: number): Observable<ResultModel<UserModel>> {
        return this.http.get<ResultModel<UserModel>>(`${API_USER_URL}/UserAvatarUpdate/${id}/${fileId}`);
    }

    userAddressList(userId: number): Observable<ResultModel<UserAddressModel[]>> {
        return this.http.get<ResultModel<UserAddressModel[]>>(`${API_USER_URL}/UserAddressList/${userId}`);
    }

    userAddressSave(data: UserAddressModel): Observable<ResultModel<UserAddressModel>> {
        return this.http.post<ResultModel<UserAddressModel>>(`${API_USER_URL}/UserAddressSave`, data);
    }

    userAddressUpdate(data: UserAddressModel): Observable<ResultModel<UserAddressModel>> {
        return this.http.post<ResultModel<UserAddressModel>>(`${API_USER_URL}/UserAddressUpdate`, data);
    }

    userAddressDelete(id: number): Observable<ResultModel<UserAddressModel[]>> {
        return this.http.delete<ResultModel<UserAddressModel[]>>(`${API_USER_URL}/UserAddressDelete/${id}`);
    }

    getUserAddressById(id: number): Observable<ResultModel<UserAddressModel>> {
        return this.http.get<ResultModel<UserAddressModel>>(`${API_USER_URL}/UserAddressById/${id}`);
    }
}
