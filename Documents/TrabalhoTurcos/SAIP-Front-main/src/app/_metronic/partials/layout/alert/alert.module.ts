import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { InlineSVGModule } from 'ng-inline-svg-2';
import { NgbAlertModule } from '@ng-bootstrap/ng-bootstrap';
import { AlertComponent } from './alert.component';
import { TranslationModule } from 'src/app/modules/i18n/translation.module';

@NgModule({
  declarations: [
    AlertComponent
  ],
  exports: [
    AlertComponent,
  ],
  imports: [
    CommonModule,
    TranslationModule,
    InlineSVGModule,
    NgbAlertModule
  ],
})
export class AlertModule {}
