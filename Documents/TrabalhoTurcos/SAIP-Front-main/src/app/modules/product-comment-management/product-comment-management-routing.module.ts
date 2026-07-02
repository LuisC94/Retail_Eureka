import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';
import { ProductCommentManagementComponent } from './product-comment-management.component';

const routes: Routes = [
  {
    path: ':id',
    component: ProductCommentManagementComponent
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class ProductCommentManagementRoutingModule {}
