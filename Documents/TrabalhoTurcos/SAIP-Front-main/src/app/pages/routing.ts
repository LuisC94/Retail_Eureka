import { Routes } from '@angular/router';
import { AuthGuard } from '../modules/auth/services/auth.guard';

const Routing: Routes = [
  {
    path: 'dashboard',
    canActivate: [AuthGuard],
    loadChildren: () =>
      import('./dashboard/dashboard.module').then((m) => m.DashboardModule),
  },
  {
    path: 'profile',
    canActivate: [AuthGuard],
    loadChildren: () =>
      import('../modules/account/account.module').then((m) => m.AccountModule),
  },
  {
    path: 'organizationmanagement',
    canActivate: [AuthGuard],
    loadChildren: () =>
      import('../modules/organization-management/organization-management.module').then((m) => m.OrganizationManagementModule),
  },
  {
    path: 'usermanagement',
    canActivate: [AuthGuard],
    loadChildren: () =>
      import('../modules/user-management/user-management.module').then((m) => m.UserManagementModule),
  },
  {
    path: 'productmanagement',
    canActivate: [AuthGuard],
    loadChildren: () =>
      import('../modules/product-management/product-management.module').then((m) => m.ProductManagementModule),
  },
  {
    path: 'shopping',
    loadChildren: () =>
      import('../modules/shopping/shopping.module').then((m) => m.ShoppingModule),
  },
  {
    path: 'basketmanagement',
    loadChildren: () =>
      import('../modules/basket-management/basket-management.module').then((m) => m.BasketManagementModule),
  },
  {
    path: 'ordermanagement',
    canActivate: [AuthGuard],
    loadChildren: () =>
      import('../modules/order-management/order-management.module').then((m) => m.OrderManagementModule),
  },
  {
    path: 'ordercompletion',
    canActivate: [AuthGuard],
    loadChildren: () =>
      import('../modules/order-completion/order-completion.module').then((m) => m.OrderCompletionModule),
  },
  {
    path: 'incomingordermanagement',
    canActivate: [AuthGuard],
    loadChildren: () =>
      import('../modules/coming-order-management/coming-order-management.module').then((m) => m.ComingOrderManagementModule),
  },
  {
    path: 'comments',
    loadChildren: () =>
      import('../modules/product-comment-management/product-comment-management.module').then((m) => m.ProductCommentManagementModule),
  },
  {
    path: '',
    redirectTo: '/shopping',
    pathMatch: 'full',
  },
  {
    path: '**',
    redirectTo: 'error/404',
  },
];

export { Routing };
