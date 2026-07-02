import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { TranslationModule } from '../i18n/translation.module';
import { ModalsModule } from 'src/app/_metronic/partials';
import { ConfirmationModule } from '../confirmation/confirmation.module';
import { InlineSVGModule } from 'ng-inline-svg-2';
import { NgbPaginationModule } from '@ng-bootstrap/ng-bootstrap';
import { ProductCommentManagementComponent } from './product-comment-management.component';
import { ProductCommentManagementRoutingModule } from './product-comment-management-routing.module';

@NgModule({
  declarations: [
    ProductCommentManagementComponent,
  ],
  imports: [
    ConfirmationModule,
    CommonModule,
    TranslationModule,
    ProductCommentManagementRoutingModule,
    FormsModule,
    ReactiveFormsModule,
    HttpClientModule,
    ModalsModule,
    InlineSVGModule,
    NgbPaginationModule
  ]
})
export class ProductCommentManagementModule {}
