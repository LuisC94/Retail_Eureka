import { Component, OnInit } from '@angular/core';
import { Observable } from 'rxjs';
import { AuthService, UserType } from '../../auth';
import { UserModel } from '../../user-management/models/user.model';
import { UserManagementService } from '../../user-management/user-management.service';

@Component({
  selector: 'app-settings',
  templateUrl: './settings.component.html',
})
export class SettingsComponent implements OnInit {
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
