import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { TranslationModule } from '../i18n/translation.module';
import { ShoppingComponent } from './shopping.component';
import { InlineSVGModule } from 'ng-inline-svg-2';
import { NgbPaginationModule } from '@ng-bootstrap/ng-bootstrap';
import { ShoppingRoutingModule } from './shopping-routing.module';
import { ProductListModule } from '../common/product-list/product-list.module';
import { ProductCarouselModule } from '../common/product-carousel/product-carousel.module';
import { ShoppingAllProductsComponent } from './all-products/all-products.component';

@NgModule({
  declarations: [
    ShoppingComponent,
    ShoppingAllProductsComponent
  ],
  imports: [
    CommonModule,
    TranslationModule,
    ShoppingRoutingModule,
    FormsModule,
    ReactiveFormsModule,
    HttpClientModule,
    InlineSVGModule,
    NgbPaginationModule,
    ProductListModule,
    ProductCarouselModule
  ]
})
export class ShoppingModule {}
