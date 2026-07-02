import { NgModule } from "@angular/core";
import { ProductCarouselComponent } from "./product-carousel.component";
import { CommonModule } from "@angular/common";
import { HttpClientModule } from "@angular/common/http";
import { FormsModule, ReactiveFormsModule } from "@angular/forms";
import { NgbPaginationModule } from "@ng-bootstrap/ng-bootstrap";
import { InlineSVGModule } from "ng-inline-svg-2";
import { TranslationModule } from "../../i18n";

@NgModule({
    declarations: [
      ProductCarouselComponent
    ],
    exports: [
        ProductCarouselComponent,
    ],
    imports: [
      NgbPaginationModule,
      CommonModule,
      TranslationModule,
      FormsModule,
      ReactiveFormsModule,
      HttpClientModule,
      InlineSVGModule,
    ],
  })
  export class ProductCarouselModule {}