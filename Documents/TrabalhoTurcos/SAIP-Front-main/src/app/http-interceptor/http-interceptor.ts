import { HttpInterceptor, HttpRequest, HttpHandler, HttpErrorResponse, HttpEvent } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { environment } from 'src/environments/environment';
import { AuthModel } from '../modules/auth/models/auth.model';
import { AuthHTTPService } from '../modules/auth/services/auth-http';
import { Router } from '@angular/router';
import { Observable, catchError, map, switchMap } from 'rxjs';
import { ResultModel } from '../models/result.model';

@Injectable({ providedIn: 'root' })
export class Interceptor implements HttpInterceptor {
    private authLocalStorageToken = `${environment.appVersion}-${environment.USERDATA_KEY}`;

    constructor(private router: Router, private authHttpService: AuthHTTPService) { }

    intercept(request: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {

        let currentUser = localStorage.getItem(this.authLocalStorageToken)

        var user: AuthModel = currentUser ? JSON.parse(currentUser) : '';
        const token = user.accessToken
        let requestWithToken = request.clone({
            setHeaders: {
                Authorization: `Bearer ${token}`,
            }
        });

        return next.handle(requestWithToken).pipe(
            catchError((requestError: HttpErrorResponse) => {
                if (requestError.status === 401) {
                    return this.authHttpService.refreshToken(user.accessToken, user.refreshToken).pipe(
                        switchMap((response: ResultModel<any>) => {
                            if (response.isSuccess && response.data.refreshToken != null) {
                                user.accessToken = response.data.accessToken;
                                user.refreshToken = response.data.refreshToken;
                                localStorage.setItem(this.authLocalStorageToken, JSON.stringify(user));

                                requestWithToken = request.clone({
                                    setHeaders: {
                                        Authorization: `Bearer ${user.accessToken}`,
                                    }
                                });
                            }
                            else {
                                localStorage.removeItem(this.authLocalStorageToken);
                                this.router.navigate(['/auth/login'], {
                                    queryParams: {},
                                });
                                document.location.reload();
                            }

                            return next.handle(requestWithToken).pipe(
                                catchError((requestError: HttpErrorResponse) => {
                                    if (requestError.status === 403) {
                                        this.router.navigate(['/error/500']);
                    
                                        return next.handle(requestWithToken);
                                    }
                                    else{
                                        return next.handle(requestWithToken);
                                    }
                                }));
                        })
                    );
                }
                else if (requestError.status === 403) {
                    this.router.navigate(['/error/500']);

                    return next.handle(requestWithToken);
                }
                else {
                    return next.handle(requestWithToken);
                }
            }));
    }
}