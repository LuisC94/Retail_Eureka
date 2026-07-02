import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { TranslationModule } from '../i18n/translation.module';
import { ModalsModule } from 'src/app/_metronic/partials';
import { ConfirmationModule } from '../confirmation/confirmation.module';
import { InlineSVGModule } from 'ng-inline-svg-2';
import { NgbPaginationModule } from '@ng-bootstrap/ng-bootstrap';
import { ComingOrderManagementRoutingModule } from './coming-order-management-routing.module';
import { ComingOrderManagementComponent } from './coming-order-management.component';
import { ComingOrderDetailComponent } from './detail/coming-order-detail.component';
import { StatusComponent } from './detail/status/status.component';
import { InvoiceComponent } from './detail/invoice/invoice.component';
import { PdfViewerModule } from 'ng2-pdf-viewer';
import { DataTableModule } from '../common/datatable/datatable.module';

@NgModule({
  declarations: [
    ComingOrderManagementComponent,
    ComingOrderDetailComponent,
    StatusComponent,
    InvoiceComponent
  ],
  imports: [
    DataTableModule,
    ConfirmationModule,
    CommonModule,
    TranslationModule,
    ComingOrderManagementRoutingModule,
    FormsModule,
    ReactiveFormsModule,
    HttpClientModule,
    ModalsModule,
    InlineSVGModule,
    NgbPaginationModule,
    PdfViewerModule
  ]
})
export class ComingOrderManagementModule {}
