import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';
import { ComingOrderManagementComponent } from './coming-order-management.component';
import { ComingOrderDetailComponent } from './detail/coming-order-detail.component';

const routes: Routes = [
  {
    path: '',
    children: [
      {
        path: '',
        component: ComingOrderManagementComponent
      },
      {
        path: ':id',
        component: ComingOrderDetailComponent,
      },
    ]
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class ComingOrderManagementRoutingModule {}
