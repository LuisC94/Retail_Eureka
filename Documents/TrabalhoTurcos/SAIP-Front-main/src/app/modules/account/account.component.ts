import { Component, OnInit } from '@angular/core';
import { AuthService, UserType } from '../auth';
import { UserManagementService } from '../user-management/user-management.service';
import { UserModel } from '../user-management/models/user.model';

@Component({
  selector: 'app-account',
  templateUrl: './account.component.html',
})
export class AccountComponent implements OnInit {

  user: UserType;
  userData: UserModel;

  constructor(private auth: AuthService, private userManagementService: UserManagementService) {}

  ngOnInit(): void {
    this.auth.currentUserSubject.subscribe(result => {
      this.user = result;

      this.userManagementService.updateUser(this.user?.id!);

      this.userManagementService.user$.subscribe(result => {
        this.userData = result!;
      });
    });
  }
}
