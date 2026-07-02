import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';
import { BasketManagementComponent } from './basket-management.component';

const routes: Routes = [
  {
    path: '',
    component: BasketManagementComponent
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class BasketManagementRoutingModule {}
