import { Component, OnInit, OnDestroy } from '@angular/core';
import { FormGroup, FormBuilder, Validators } from '@angular/forms';
import { Subscription, Observable } from 'rxjs';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { ConfirmPasswordValidator } from './confirm-password.validator';
import { first } from 'rxjs/operators';
import { UserModel } from 'src/app/modules/user-management/models/user.model';

enum ErrorStates {
  NotSubmitted,
  HasError,
  NoError,
}

export type RegistrationTabsType =
  | 'bireysel'
  | 'kurumsal';

@Component({
  selector: 'app-registration',
  templateUrl: './registration.component.html',
  styleUrls: ['./registration.component.scss']
})
export class RegistrationComponent implements OnInit, OnDestroy {
  registrationForm: FormGroup;
  errorState: ErrorStates = ErrorStates.NotSubmitted;
  errorStates = ErrorStates;
  isLoading$: Observable<boolean>;

  activeTabId: RegistrationTabsType = "bireysel";
  // private fields
  private unsubscribe: Subscription[] = []; // Read more: => https://brianflove.com/2016/12/11/anguar-2-unsubscribe-observables/

  constructor(
    private fb: FormBuilder,
    private authService: AuthService,
    private router: Router
  ) {
    this.isLoading$ = this.authService.isLoading$;
    // redirect to home if already logged in
    if (this.authService.currentUserValue) {
      this.router.navigate(['/']);
    }
  }

  ngOnInit(): void {
    this.initForm();
  }

  // convenience getter for easy access to form fields
  get f() {
    return this.registrationForm.controls;
  }

  initForm() {
    this.registrationForm = this.fb.group(
      {
        name: [
          "",
          Validators.compose([
            Validators.required,
          ]),
        ],
        surname: [
          "",
          Validators.compose([
            Validators.required,
          ]),
        ],
        email: [
          '',
          Validators.compose([
            Validators.required,
            Validators.email,
            Validators.minLength(3),
            Validators.maxLength(320), // https://stackoverflow.com/questions/386294/what-is-the-maximum-length-of-a-valid-email-address
          ]),
        ],
        password: [
          '',
          Validators.compose([
            Validators.required,
            Validators.minLength(3),
            Validators.maxLength(100),
          ]),
        ],
        cPassword: [
          '',
          Validators.compose([
            Validators.required,
            Validators.minLength(3),
            Validators.maxLength(100),
          ]),
        ],
        phone: [
          "",
          Validators.compose([
            Validators.required,
          ]),
        ],
        username: [
          "",
          Validators.compose([
            Validators.required,
          ]),
        ],
        isProducer: [
          false,
          Validators.compose([
            Validators.required,
          ]),
        ]
      },
      {
        validator: ConfirmPasswordValidator.MatchPassword,
      }
    );
  }

  setActiveTabId(tabId: RegistrationTabsType) {
    this.activeTabId = tabId;

    if(this.activeTabId == 'kurumsal') {
      this.initForm();
    }
  }

  submit() {
    var newUser = this.registrationForm.getRawValue() as UserModel;

    const registrationSubscr = this.authService
      .registration(newUser)
      .pipe(first())
      .subscribe((result: boolean) => {
        this.errorState = result ? ErrorStates.NoError : ErrorStates.HasError;

        if (result) {
          setTimeout(() => {
            this.router.navigate(["/auth/login"]);
          }, 2000);
        }
      });
    this.unsubscribe.push(registrationSubscr);
  }

  ngOnDestroy() {
    this.unsubscribe.forEach((sb) => sb.unsubscribe());
  }
}
