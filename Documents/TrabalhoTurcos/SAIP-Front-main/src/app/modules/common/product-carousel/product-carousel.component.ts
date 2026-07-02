import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges, ViewChild } from "@angular/core";
import { PaginationModel } from "src/app/models/pagination.model";
import { ProductModel } from "../../shopping/models/product.model";
import { BasketModel } from "../../shopping/models/basket.model";
import { AuthService } from "../../auth";
import { BasketService } from "src/app/_metronic/partials/layout/basket/basket.service";
import { BasketManagementService } from "../../basket-management/basket-management.service";
import { Router } from "@angular/router";
import { AlertService } from "src/app/_metronic/partials/layout/alert/alert.service";

@Component({
  selector: 'app-product-carousel',
  templateUrl: './product-carousel.component.html',
  styleUrls: ['./product-carousel.component.scss']
})
export class ProductCarouselComponent implements OnChanges {

  @Input() items: any[];
  @Input() header: string;
  @Input() id: string;

  itemsMap: Map<string, any[]> = new Map<string, any[]>();
  itemKeys: string[] = [];

  prevButtonDisabled: boolean = false;
  nextButtonDisabled: boolean = false;
  activeCarouselIndex: number = 1;
  totalCarouselIndex: number = 1;

  constructor(
    private alertService: AlertService,
    private basketService: BasketService,
    private basketManagementService: BasketManagementService,
    private router: Router,
    private authService: AuthService
  ) {

  }

  addToBasket(item: ProductModel) {
    var currentUser = this.authService.currentUserValue;

    if (currentUser) {
      let data: BasketModel = { id: 0, userId: currentUser.id, productId: item.id, isDeleted: false, product: undefined, totalPrice: undefined, numberOf: undefined };

      this.basketManagementService.save(data).subscribe(result => {
        if (result.isSuccess) {
          this.alertService.createAlert("success", result.message);
          this.basketService.loadBasketFromDb();
        }
        else {
          this.alertService.createAlert("danger", result.message);
        }
      })
    }
    else {
      var basket = JSON.parse(localStorage.getItem("basket") as string) as BasketModel[];

      if (basket) {
        if (basket.length < 15) {
          basket.push({ id: 0, userId: 0, product: item, productId: item.id, isDeleted: false, numberOf: 0, totalPrice: 0 });
        }
        else {
          this.alertService.createAlert("warning", "Daha fazla ürün eklemek için lütfen giriş yapınız!");
        }
      }
      else {
        basket = [{ id: 0, userId: 0, product: item, productId: item.id, isDeleted: false, numberOf: 0, totalPrice: 0 }];
      }

      this.basketService.setBasket(basket);
    }
  }

  goToComments(id: number) {
    if(this.authService.currentUserValue) {
      this.router.navigate(['comments/' + id]);
    }
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes.items && changes.items.currentValue) {
      this.items = changes.items.currentValue;
      this.itemsMap.clear();

      let i: number = 1;
      let list: any[] = [];
      this.items.forEach(item => {
        list.push(item);
        
        if (i % 4 == 0) {
          if (i == 4) {
            this.itemsMap.set("active" + (i), list);
            this.itemKeys.push("active" + (i));
          }
          else {
            this.itemsMap.set("inactive" + (i), list);
            this.itemKeys.push("inactive" + (i));
          }

          list = [];
        }

        // items count > 4 ve items count % 4 != 0 ise
        if((i % 4) != 0 && i == this.items.length && this.itemsMap.size > 0) {
          this.itemsMap.set("inactive" + (i), list);
          this.itemKeys.push("inactive" + (i));
        }
        // items count < 4 ise
        else if(i == this.items.length && this.itemsMap.size == 0) {
          this.itemsMap.set("active4", list);
          this.itemKeys.push("active4");
        }
        
        i++;
      })

      if(this.items.length < 5) {
        this.nextButtonDisabled = true;
        this.prevButtonDisabled = true;
      } 
      else{
        this.prevButtonDisabled = true;
        this.nextButtonDisabled = false;
      }

      this.totalCarouselIndex = Math.ceil(this.items.length / 4);
    }
  }

  onNextButtonClick() {
    this.prevButtonDisabled = false;
    this.activeCarouselIndex += 1;
    
    if(this.totalCarouselIndex > this.activeCarouselIndex) {
      this.nextButtonDisabled = false;
    }
    else{
      this.nextButtonDisabled = true;
    }
  }

  onPrevButtonClick() {
    this.activeCarouselIndex -= 1;

    if(this.activeCarouselIndex == 1) {
      this.prevButtonDisabled = true;

      if(this.totalCarouselIndex > this.activeCarouselIndex) {
        this.nextButtonDisabled = false;
      }
      else{
        this.nextButtonDisabled = true;
      }
    }
    else{
      this.prevButtonDisabled = false;

      if(this.totalCarouselIndex > this.activeCarouselIndex) {
        this.nextButtonDisabled = false;
      }
      else{
        this.nextButtonDisabled = true;
      }
    }
  }

  goToAllProducts() {
    this.router.navigate(['shopping/all']);
  }
}