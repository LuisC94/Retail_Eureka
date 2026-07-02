import { NgModule } from "@angular/core";
import { ProductListComponent } from "./product-list.component";
import { CommonModule } from "@angular/common";
import { HttpClientModule } from "@angular/common/http";
import { FormsModule, ReactiveFormsModule } from "@angular/forms";
import { NgbPaginationModule } from "@ng-bootstrap/ng-bootstrap";
import { InlineSVGModule } from "ng-inline-svg-2";
import { TranslationModule } from "../../i18n";
import { ProductCarouselModule } from "../product-carousel/product-carousel.module";

@NgModule({
    declarations: [
      ProductListComponent
    ],
    exports: [
        ProductListComponent,
    ],
    imports: [
      NgbPaginationModule,
      CommonModule,
      TranslationModule,
      FormsModule,
      ReactiveFormsModule,
      HttpClientModule,
      InlineSVGModule,
      ProductCarouselModule
    ],
  })
  export class ProductListModule {}