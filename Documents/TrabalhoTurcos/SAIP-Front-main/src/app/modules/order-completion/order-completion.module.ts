import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { TranslationModule } from '../i18n/translation.module';
import { ModalsModule } from 'src/app/_metronic/partials';
import { ConfirmationModule } from '../confirmation/confirmation.module';
import { InlineSVGModule } from 'ng-inline-svg-2';
import { NgbPaginationModule } from '@ng-bootstrap/ng-bootstrap';
import { OrderCompletionRoutingModule } from './order-completion-routing.module';
import { OrderCompletionComponent } from './order-completion.component';
import { AddressEditSaveComponent } from '../account/addresses/forms/list/edit-save/edit-save.component';
import { AccountModule } from '../account/account.module';

@NgModule({
  declarations: [
    OrderCompletionComponent
  ],
  imports: [
    ConfirmationModule,
    CommonModule,
    TranslationModule,
    OrderCompletionRoutingModule,
    FormsModule,
    ReactiveFormsModule,
    HttpClientModule,
    ModalsModule,
    InlineSVGModule,
    NgbPaginationModule,
    AccountModule
  ]
})
export class OrderCompletionModule {}
