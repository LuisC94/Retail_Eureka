import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';
import { OrderManagementComponent } from './order-management.component';
import { OrderDetailComponent } from './detail/order-detail.component';

const routes: Routes = [
  {
    path: '',
    children: [
      {
        path: '',
        component: OrderManagementComponent
      },
      {
        path: ':id',
        component: OrderDetailComponent,
      },
    ]
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class OrderManagementRoutingModule {}
