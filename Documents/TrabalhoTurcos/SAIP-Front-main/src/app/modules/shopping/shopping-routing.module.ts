import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';
import { ShoppingComponent } from './shopping.component';
import { ProductManagementComponent } from '../product-management/product-management.component';
import { ShoppingAllProductsComponent } from './all-products/all-products.component';

const routes: Routes = [
  {
    path: '',
    children: [
      {
        path: 'all',
        component: ShoppingAllProductsComponent
      },
      {
        path: '',
        component: ShoppingComponent,
      }
    ]
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class ShoppingRoutingModule {}
