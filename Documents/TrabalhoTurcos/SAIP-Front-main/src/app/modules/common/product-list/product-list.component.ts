import { Component, EventEmitter, Input, Output, ViewChild } from "@angular/core";
import { PaginationModel } from "src/app/models/pagination.model";
import { ProductModel } from "../../shopping/models/product.model";
import { BasketModel } from "../../shopping/models/basket.model";
import { AuthService } from "../../auth";
import { BasketService } from "src/app/_metronic/partials/layout/basket/basket.service";
import { BasketManagementService } from "../../basket-management/basket-management.service";
import { Router } from "@angular/router";
import { AlertService } from "src/app/_metronic/partials/layout/alert/alert.service";

@Component({
    selector: 'app-product-list',
    templateUrl: './product-list.component.html',
  })
  export class ProductListComponent {

    @Input() isShoppingPage: boolean;
    @Input() dataSource: any[];
    @Input() totalCount: number;
    @Input() paginationModel: PaginationModel;
    @Input() hasEditPermission: boolean;
    @Input() hasDeletePermission: boolean;
    @Output() paginationModelChange: EventEmitter<PaginationModel> = new EventEmitter<PaginationModel>();
    @Output() editButtonClick: EventEmitter<number> = new EventEmitter<number>();
    @Output() deleteButtonClick: EventEmitter<number> = new EventEmitter<number>();

    constructor(
      private authService: AuthService, 
      private basketService: BasketService,
      private basketManagementService: BasketManagementService,
      private router: Router,
      private alertService: AlertService
    ) {
    }

    addToBasket(item: ProductModel) {
      var currentUser = this.authService.currentUserValue;
  
      if(currentUser) {
        let data: BasketModel = {id: 0, userId: currentUser.id, productId: item.id, isDeleted: false, product: undefined, totalPrice: undefined, numberOf: undefined};
  
        this.basketManagementService.save(data).subscribe(result => {
          if(result.isSuccess) {
            this.alertService.createAlert("success", result.message);
            this.basketService.loadBasketFromDb();
          }
          else{
              this.alertService.createAlert("danger", result.message);
          }
        })
      }
      else{
        var basket = JSON.parse(localStorage.getItem("basket") as string) as BasketModel[];
  
        if(basket) {
          if(basket.length < 15) {
            basket.push({id: 0, userId: 0, product: item, productId: item.id, isDeleted: false, numberOf: 0, totalPrice: 0});
          }
          else{
            this.alertService.createAlert("warning", "Daha fazla ürün eklemek için lütfen giriş yapınız!");
          }
        }
        else{
          basket = [{id: 0, userId: 0, product: item, productId: item.id, isDeleted: false, numberOf: 0, totalPrice: 0}];
        }
  
        this.basketService.setBasket(basket);
      }
    }

    goToComments(id:number) {
      if(this.authService.currentUserValue) {
        this.router.navigate(['comments/' + id]);
      }
    }

    openDeleteModal(id: number) {
      this.deleteButtonClick.emit(id);
    }
  
    openEditModal(id: number) {
      this.editButtonClick.emit(id);
    }

    onPageChanges() {
      this.paginationModelChange.emit(this.paginationModel);
    }
  }