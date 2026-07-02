import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { TranslationModule } from '../i18n/translation.module';
import { ModalsModule } from 'src/app/_metronic/partials';
import { ConfirmationModule } from '../confirmation/confirmation.module';
import { ProductManagementComponent } from './product-management.component';
import { ProductManagementRoutingModule } from './product-management-routing.module';
import { InlineSVGModule } from 'ng-inline-svg-2';
import { NgbAlertModule, NgbPaginationModule } from '@ng-bootstrap/ng-bootstrap';
import { ProductEditSaveComponent } from './edit-save/edit-save.component';
import { ProductListModule } from '../common/product-list/product-list.module';
import { DataTableModule } from '../common/datatable/datatable.module';

@NgModule({
  declarations: [
    ProductManagementComponent,
    ProductEditSaveComponent
  ],
  imports: [
    DataTableModule,
    ConfirmationModule,
    CommonModule,
    TranslationModule,
    ProductManagementRoutingModule,
    FormsModule,
    ReactiveFormsModule,
    HttpClientModule,
    ModalsModule,
    InlineSVGModule,
    NgbPaginationModule,
    ProductListModule,
    NgbAlertModule
  ]
})
export class ProductManagementModule {}
