import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { UserModelAuth } from '../../models/user.model';
import { environment } from '../../../../../environments/environment';
import { AuthModel } from '../../models/auth.model';
import { ResultModel } from 'src/app/models/result.model';
import { UserModel } from 'src/app/modules/user-management/models/user.model';

const API_USERS_URL = `${environment.apiUrl}/auth`;

@Injectable({
  providedIn: 'root',
})
export class AuthHTTPService {
  constructor(private http: HttpClient) {}

  // public methods
  login(username: string, password: string): Observable<any> {
    return this.http.post<AuthModel>(`${API_USERS_URL}/login`, {
      username,
      password,
    });
  }

  refreshToken(accessToken: string, refreshToken: string): Observable<any> {
    return this.http.post<AuthModel>(`${API_USERS_URL}/RefreshToken`, {
      accessToken,
      refreshToken,
    });
  }

  // CREATE =>  POST: add a new user to the server
  createUser(user: UserModel): Observable<ResultModel<UserModel>> {
    return this.http.post<ResultModel<UserModel>>(`${API_USERS_URL}/Register`, user);
  }

  // Your server should check email => If email exists send link to the user and return true | If email doesn't exist return false
  forgotPassword(email: string): Observable<any> {
    return this.http.post<any>(`${API_USERS_URL}/ForgotPassword`, {
      email,
    });
  }

  resetPassword(id: number, password: string): Observable<any> {
    return this.http.post<any>(`${API_USERS_URL}/ResetPassword`, {
      id,
      password
    });
  }

  changePassword(id: number, currentPassword: string, password: string): Observable<ResultModel<boolean>> {
    return this.http.post<any>(`${API_USERS_URL}/ChangePassword`, {
      id,
      currentPassword,
      password,
    });
  }

  getUserByToken(token: string): Observable<UserModelAuth> {
    const httpHeaders = new HttpHeaders({
      Authorization: `Bearer ${token}`,
    });
    return this.http.get<UserModelAuth>(`${API_USERS_URL}/me`, {
      headers: httpHeaders,
    });
  }
}
