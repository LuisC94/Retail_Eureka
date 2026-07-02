import { Component, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { ConfirmationComponent } from '../confirmation/confirmation.component';
import { BasketService } from 'src/app/_metronic/partials/layout/basket/basket.service';
import { BasketManagementService } from './basket-management.service';
import { BasketModel } from './models/basket.model';
import { Router } from '@angular/router';
import { AuthService } from '../auth';
import { OrderManagementService } from '../order-management/order-management.service';
import { OrderModel } from '../order-management/models/order.model';
import { NotificationService } from 'src/app/_metronic/partials/layout/extras/dropdown-inner/notifications-inner/notification.service';
import { AlertService } from 'src/app/_metronic/partials/layout/alert/alert.service';
import { TranslateService } from '@ngx-translate/core';

@Component({
  selector: 'app-basket-management',
  templateUrl: './basket-management.component.html',
  styleUrls: ['./basket-management.component.scss'],
})
export class BasketManagementComponent implements OnInit, OnDestroy {

  @ViewChild('deleteConfirmationComponent') private deleteConfirmationComponent: ConfirmationComponent;

  currentUserIsExist: boolean = false;
  currentUser: any;

  header: string = "Sepetim";
  basket: BasketModel[] = [];
  basketFromStorage: BasketModel[] = [];
  numberOfItem: number = 0;
  totalPrice: number = 0;

  constructor(
    private authService: AuthService, 
    private basketService: BasketService,
    private basketManagementService: BasketManagementService, 
    private orderManagementService: OrderManagementService,
    private alertService: AlertService,
    private router: Router,
    private translate: TranslateService) {
  }

  addOne(productId: number | undefined) {
    if(this.currentUserIsExist) {
      let data: BasketModel = {id: 0, userId: this.currentUser.id, productId: productId, isDeleted: false, product: undefined, totalPrice: undefined, numberOf: undefined};
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
      if(this.basketFromStorage.length < 15) {
        let itemToAdd = this.basketFromStorage.filter(f => f.productId == productId)[0];
        this.basketFromStorage.push(itemToAdd);
        this.basketService.setBasket(this.basketFromStorage);
      }
      else{
        this.alertService.createAlert("warning", "Daha fazla ürün eklemek için lütfen giriş yapınız!");
      }
    }
  }


  confirmBasket() {
    if(!this.currentUserIsExist) {
      this.router.navigate(['/auth/login']);
    }
    else{
      this.router.navigate(['/ordercompletion']);

      // let data: OrderModel = { id: 0, basketId: this.basketFromStorage[0].id, userId: this.currentUser.id, price: this.totalPrice};

      // this.orderManagementService.save(data).subscribe(result => {
      //   if(result.isSuccess) {
      //     this.basketService.loadBasketFromDb();
      //     this.alertService.createAlert("success", result.message);

      //     // this.notificationService.updateNotifications(this.currentUser.id);
      //   }
      //   else{
      //       this.alertService.createAlert("danger", result.message);
      //   }
      // })
    }
  }

  delete(event: number) {
    if(this.currentUserIsExist) {
      var id = this.basketFromStorage.filter(f => f.productId == event)[0].id;

      this.basketManagementService.deleteAll(id, event).subscribe(result => {
        if(result.isSuccess) {
          this.basketService.loadBasketFromDb();
          this.alertService.createAlert("success", result.message);
        }
        else{
            this.alertService.createAlert("danger", result.message);
        }
      })
    }
    else{
      let temp: BasketModel[] = [];
      this.basketFromStorage.forEach(item => {
        if(item.productId != event) {
          temp.push(item);
        }
      })

      this.basketService.setBasket(temp);
    }
  }

  deleteOne(productId: number |undefined) {
    if(this.currentUserIsExist) {
      var id = this.basketFromStorage.filter(f => f.productId == productId)[0].id;

      this.basketManagementService.delete(id, productId!).subscribe(result => {
        if(result.isSuccess) {
          this.basketService.loadBasketFromDb();
          this.alertService.createAlert("success", result.message);
        }
        else{
            this.alertService.createAlert("danger", result.message);
        }
      })
    }
    else{
      let i: number = 0;
      let index: number = -1;
      this.basketFromStorage.forEach(item => {
        if(item.productId == productId) {
          if(index == -1) {
            index = i;
          }
        }

        i++;
      });

      if(index > -1) {
        this.basketFromStorage.splice(index, 1);
        this.basketService.setBasket(this.basketFromStorage);
      }
    }
  }

  ngOnDestroy(): void {
  }

  ngOnInit(): void {
    const currentUser = this.authService.currentUserValue;
    if (currentUser) {
      this.currentUserIsExist = true;
      this.currentUser = currentUser;
      this.basketService.loadBasketFromDb();
    }
    else{
      this.currentUserIsExist = false;
    }

    this.basketService.basket$.subscribe(result => {
      if(result) {
        this.numberOfItem = 0;
        this.totalPrice = 0;
        this.basket = [];

        this.basketFromStorage = result;

        result.forEach(item => {
          this.numberOfItem += 1;
          this.totalPrice += item.product?.sale! > 0 ? item.product?.discountedPrice! : item.product?.price!;
          
          if(this.basket.length == 0) {
            this.basket.push({id: 0, userId: 0, productId: item.product?.id, product: item.product, numberOf: 1, isDeleted: item.isDeleted, totalPrice: item.product?.sale! > 0 ? item.product?.discountedPrice : item.product?.price});
          }
          else{
            let itemInBasket = this.basket.filter(f => f.productId == item.productId);
            if(itemInBasket.length > 0) {
              if(itemInBasket[0].numberOf) { itemInBasket[0].numberOf += 1; }
              if(itemInBasket[0].totalPrice) { itemInBasket[0].totalPrice += item.product?.sale! > 0 ? item.product?.discountedPrice! : item.product?.price!; }
            }
            else{
              this.basket.push({id: 0, userId: 0, productId: item.product?.id, product: item.product, numberOf: 1, isDeleted: item.isDeleted, totalPrice: item.product?.sale! > 0 ? item.product?.discountedPrice : item.product?.price});
            }
          }
        })
      }
    });
  }

  openDeleteModal(id: number | undefined) {
    var deleteText = "";
    this.translate.get('DELETE').subscribe((translation)=> {
      deleteText = translation
    })
    this.deleteConfirmationComponent.openModal(deleteText, id);
  }

  routeToShopping() {
    this.router.navigate(['/shopping']);
  }
}
