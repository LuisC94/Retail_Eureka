import { Injectable, OnDestroy } from '@angular/core';
import { Observable, BehaviorSubject, of, Subscription } from 'rxjs';
import { map, catchError, switchMap, finalize } from 'rxjs/operators';
import { UserModelAuth } from '../models/user.model';
import { UserModel } from '../../user-management/models/user.model';
import { AuthModel } from '../models/auth.model';
import { AuthHTTPService } from './auth-http';
import { environment } from 'src/environments/environment';
import { Router } from '@angular/router';
import { ResultModel } from 'src/app/models/result.model';
import { WebSocketService } from '../../common/web-socket.service';

export type UserType = UserModelAuth | undefined;

@Injectable({
  providedIn: 'root',
})
export class AuthService implements OnDestroy {
  // private fields
  private unsubscribe: Subscription[] = []; // Read more: => https://brianflove.com/2016/12/11/anguar-2-unsubscribe-observables/
  private authLocalStorageToken = `${environment.appVersion}-${environment.USERDATA_KEY}`;

  // public fields
  currentUser$: Observable<UserType>;
  isLoading$: Observable<boolean>;
  currentUserSubject: BehaviorSubject<UserType>;
  isLoadingSubject: BehaviorSubject<boolean>;

  get currentUserValue(): UserType {
    return this.currentUserSubject.value;
  }

  set currentUserValue(user: UserType) {
    this.currentUserSubject.next(user);
  }

  constructor(
    private authHttpService: AuthHTTPService,
    private router: Router,
    private wsService: WebSocketService
  ) {
    this.isLoadingSubject = new BehaviorSubject<boolean>(false);
    this.currentUserSubject = new BehaviorSubject<UserType>(undefined);
    this.currentUser$ = this.currentUserSubject.asObservable();
    this.isLoading$ = this.isLoadingSubject.asObservable();
    const subscr = this.getUserByToken().subscribe();
    this.unsubscribe.push(subscr);
  }

  // public methods
  login(email: string, password: string): Observable<UserType> {
    this.isLoadingSubject.next(true);
    return this.authHttpService.login(email, password).pipe(
      map((result: ResultModel<AuthModel>) => {
        if(result.isSuccess) {
          const auth = this.setAuthFromLocalStorage(result.data);
          return auth;
        }
        else{
          return of(result.message);
        }
      }),
      switchMap(() => this.getUserByToken()),
      catchError((err) => {
        console.error('err', err);
        return of(undefined);
      }),
      finalize(() => this.isLoadingSubject.next(false))
    );
  }

  logout() {
    this.wsService.closeWebSocket();
    localStorage.removeItem("basket");
    localStorage.removeItem(this.authLocalStorageToken);
    this.currentUserSubject.next(undefined);
    this.router.navigate(['/'], {
      queryParams: {},
    });
  }

  getUserByToken(): Observable<UserType> {
    const auth = this.getAuthFromLocalStorage();
    if (!auth || !auth.accessToken) {
      return of(undefined);
    }

    this.isLoadingSubject.next(true);
    var user: UserType = JSON.parse(atob(auth.accessToken.split('.')[1]));

    if (user) {
      this.currentUserSubject.next(user);
    } else {
      this.logout();
    }
    
    this.isLoadingSubject.next(false);

    return of(user);
  }

  // need create new user then login
  registration(user: UserModel): Observable<any> {
    this.isLoadingSubject.next(true);
    return this.authHttpService.createUser(user).pipe(
      map((result: ResultModel<UserModel>) => {
        this.isLoadingSubject.next(false);
        return result.isSuccess;
      }),
      catchError((err) => {
        console.error('err', err);
        return of(undefined);
      }),
      finalize(() => this.isLoadingSubject.next(false))
    );
  }

  forgotPassword(email: string): Observable<boolean> {
    this.isLoadingSubject.next(true);
    return this.authHttpService.forgotPassword(email).pipe(
      map((result: ResultModel<string>) => {
        return result.isSuccess;
      }),
      finalize(() => this.isLoadingSubject.next(false))
    );
  }

  resetPassword(id: number, password: string): Observable<boolean> {
    this.isLoadingSubject.next(true);
    return this.authHttpService.resetPassword(id, password).pipe(
      map((result: ResultModel<boolean>) => {
        return result.isSuccess;
      }),
      finalize(() => this.isLoadingSubject.next(false))
    );
  }

  changePassword(id: number, currentPassword: string, password: string): Observable<ResultModel<boolean>> {
    this.isLoadingSubject.next(true);
    return this.authHttpService.changePassword(id, currentPassword, password).pipe(
      map((result: ResultModel<boolean>) => {
        return result;
      }),
      finalize(() => this.isLoadingSubject.next(false))
    );
  }

  // private methods
  private setAuthFromLocalStorage(auth: AuthModel): boolean {
    // store auth authToken/refreshToken/epiresIn in local storage to keep user logged in between page refreshes
    if (auth && auth.accessToken) {
      localStorage.setItem(this.authLocalStorageToken, JSON.stringify(auth));
      return true;
    }
    return false;
  }

  private getAuthFromLocalStorage(): AuthModel | undefined {
    try {
      const lsValue = localStorage.getItem(this.authLocalStorageToken);
      if (!lsValue) {
        return undefined;
      }

      const authData = JSON.parse(lsValue);
      return authData;
    } catch (error) {
      console.error(error);
      return undefined;
    }
  }

  ngOnDestroy() {
    this.unsubscribe.forEach((sb) => sb.unsubscribe());
  }
}
