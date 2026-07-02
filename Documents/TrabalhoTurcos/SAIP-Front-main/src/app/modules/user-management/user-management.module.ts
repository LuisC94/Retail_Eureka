import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { TranslationModule } from '../i18n/translation.module';
import { UserManagementComponent } from './user-management.component';
import { UserManagementRoutingModule } from './user-management-routing.module';
import { PermissionComponent } from './permission/permission.component';
import { RoleComponent } from './role/role.component';
import { UserComponent } from './user/user.component';
import { PermissionEditSaveComponent } from './permission/edit-save/edit-save.component';
import { ModalsModule } from 'src/app/_metronic/partials';
import { RoleEditSaveComponent } from './role/edit-save/edit-save.component';
import { UserEditSaveComponent } from './user/edit-save/edit-save.component';
import { ConfirmationModule } from '../confirmation/confirmation.module';
import { DataTableModule } from '../common/datatable/datatable.module';

@NgModule({
  declarations: [
    UserManagementComponent,
    PermissionComponent,
    PermissionEditSaveComponent,
    RoleComponent,
    RoleEditSaveComponent,
    UserComponent,
    UserEditSaveComponent,
  ],
  imports: [
    DataTableModule,
    ConfirmationModule,
    CommonModule,
    TranslationModule,
    UserManagementRoutingModule,
    FormsModule,
    ReactiveFormsModule,
    HttpClientModule,
    ModalsModule
  ],
})
export class UserManagementModule {}
