import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { AccountRoutingModule } from './account-routing.module';
import { AccountComponent } from './account.component';
import { SettingsComponent } from './settings/settings.component';
import { ProfileDetailsComponent } from './settings/forms/profile-details/profile-details.component';
import { ConnectedAccountsComponent } from './settings/forms/connected-accounts/connected-accounts.component';
import { DeactivateAccountComponent } from './settings/forms/deactivate-account/deactivate-account.component';
import { EmailPreferencesComponent } from './settings/forms/email-preferences/email-preferences.component';
import { NotificationsComponent } from './settings/forms/notifications/notifications.component';
import { SignInMethodComponent } from './settings/forms/sign-in-method/sign-in-method.component';
import { DropdownMenusModule, ModalsModule, WidgetsModule } from '../../_metronic/partials';
import {SharedModule} from "../../_metronic/shared/shared.module";
import { ReactiveFormsModule } from '@angular/forms';
import { TranslateModule } from '@ngx-translate/core';
import { InlineSVGModule } from 'ng-inline-svg-2';
import { AlertModule } from 'src/app/_metronic/partials/layout/alert/alert.module';
import { AddressesComponent } from './addresses/addresses.component';
import { AddressListComponent } from './addresses/forms/list/list.component';
import { ConfirmationModule } from '../confirmation/confirmation.module';
import { AddressEditSaveComponent } from './addresses/forms/list/edit-save/edit-save.component';

@NgModule({
  declarations: [
    AccountComponent,
    AddressesComponent,
    AddressListComponent,
    AddressEditSaveComponent,
    SettingsComponent,
    ProfileDetailsComponent,
    ConnectedAccountsComponent,
    DeactivateAccountComponent,
    EmailPreferencesComponent,
    NotificationsComponent,
    SignInMethodComponent,
  ],
  imports: [
    CommonModule,
    ConfirmationModule,
    AccountRoutingModule,
    DropdownMenusModule,
    WidgetsModule,
    SharedModule,
    ReactiveFormsModule,
    AlertModule,
    TranslateModule,
    InlineSVGModule,
    ModalsModule
  ],
  exports: [
    AddressEditSaveComponent
  ]
})
export class AccountModule {}
