import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';
import { OrderCompletionComponent } from './order-completion.component';

const routes: Routes = [
  {
    path: '',
    component: OrderCompletionComponent
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class OrderCompletionRoutingModule {}
