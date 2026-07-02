import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { TranslationModule } from '../i18n/translation.module';
import { ModalsModule } from 'src/app/_metronic/partials';
import { ConfirmationModule } from '../confirmation/confirmation.module';
import { InlineSVGModule } from 'ng-inline-svg-2';
import { NgbPaginationModule } from '@ng-bootstrap/ng-bootstrap';
import { BasketManagementComponent } from './basket-management.component';
import { BasketManagementRoutingModule } from './basket-management-routing.module';

@NgModule({
  declarations: [
    BasketManagementComponent,
  ],
  imports: [
    ConfirmationModule,
    CommonModule,
    TranslationModule,
    BasketManagementRoutingModule,
    FormsModule,
    ReactiveFormsModule,
    HttpClientModule,
    ModalsModule,
    InlineSVGModule,
    NgbPaginationModule
  ]
})
export class BasketManagementModule {}
