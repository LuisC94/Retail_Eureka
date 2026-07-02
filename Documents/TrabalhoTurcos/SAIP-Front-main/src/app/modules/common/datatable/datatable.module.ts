import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { DataTableComponent } from './datatable.component';
import { InlineSVGModule } from 'ng-inline-svg-2';
import { NgbPaginationModule } from '@ng-bootstrap/ng-bootstrap';
import { DropdownMenusModule } from 'src/app/_metronic/partials';
import { TranslationModule } from '../../i18n';

@NgModule({
  declarations: [
    DataTableComponent
  ],
  exports: [
    DataTableComponent,
  ],
  imports: [
    DropdownMenusModule,
    NgbPaginationModule,
    CommonModule,
    TranslationModule,
    FormsModule,
    ReactiveFormsModule,
    HttpClientModule,
    InlineSVGModule
  ],
})
export class DataTableModule {}
