import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';
import { UserManagementComponent } from './user-management.component';
import { PermissionComponent } from './permission/permission.component';
import { RoleComponent } from './role/role.component';
import { UserComponent } from './user/user.component';

const routes: Routes = [
  {
    path: '',
    component: UserManagementComponent,
    children: [
      {
        path: '',
        redirectTo: 'permissions',
        pathMatch: 'full',
      },
      {
        path: 'permissions',
        component: PermissionComponent,
      },
      {
        path: 'roles',
        component: RoleComponent,
      },
      {
        path: 'users',
        component: UserComponent,
      },
      { path: '', redirectTo: 'permissions', pathMatch: 'full' },
      { path: '**', redirectTo: 'permissions', pathMatch: 'full' },
    ],
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class UserManagementRoutingModule {}
