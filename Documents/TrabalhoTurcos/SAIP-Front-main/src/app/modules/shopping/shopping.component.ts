import { Component, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { PaginationModel } from 'src/app/models/pagination.model';
import { AuthService } from '../auth';
import { BasketService } from 'src/app/_metronic/partials/layout/basket/basket.service';
import { ShoppingService } from './shopping.service';
import { LayoutService } from 'src/app/_metronic/layout/core/layout.service';
import { LayoutInitService } from 'src/app/_metronic/layout/core/layout-init.service';
import { BasketManagementService } from '../basket-management/basket-management.service';
import { ProductModel } from './models/product.model';

@Component({
  selector: 'app-shopping',
  templateUrl: './shopping.component.html',
  styleUrls: ['./shopping.component.scss'],
})
export class ShoppingComponent implements OnInit, OnDestroy {

  headerContainerCssClasses: string;
  userId: number = 0;
  searchTerm: string = '';
  lastSearchTerm: string = '';

  constructor(private shoppingService: ShoppingService, private authService: AuthService, private basketService: BasketService,
    private layout: LayoutService, private initService: LayoutInitService, private basketManagementService: BasketManagementService

  ) {
    this.initService.init();
  }

  vegetables: ProductModel[];
  fruits: ProductModel[];
  driedFruits: ProductModel[];
  advantageous: ProductModel[];
  highScores: ProductModel[];
  recommendedProducts: ProductModel[];
  quickDeliveries: ProductModel[];
  suggestedVendors: ProductModel[];

  totalCount: number;
  paginationModel: PaginationModel;

  getUserId() {
    this.authService.currentUserSubject.asObservable().subscribe(result => {
      if (result) {
        this.userId = result.id;
      }
    });
  }

  loadBestVendors() {
    let categoryId = 7;

    this.shoppingService.paging(this.paginationModel.pageNumber, this.paginationModel.pageSize, categoryId, this.userId, this.searchTerm)
      .subscribe(result => {
        if (result.isSuccess) {
          if (result.data) {
            if (result.data.items) {
              result.data.items.forEach(item => {
                item.fileResult.fileContents = "data:" + item.fileResult.contentType + ";base64," + item.fileResult.fileContents;

                item.starsStatus = [];
                for (let i = 1; i <= 5; i++) {
                  if (i <= Math.floor(item.rating!)) {
                    item.starsStatus?.push("checked");
                  }
                  else {
                    item.starsStatus?.push("");
                  }
                }
              })
              this.suggestedVendors = result.data.items;
              this.totalCount = result.data.totalCount;
            }
            else {
              this.suggestedVendors = [];
              this.totalCount = 0;
            }
          }
          else {
            this.suggestedVendors = [];
            this.totalCount = 0;
          }
        }
        else {
          this.suggestedVendors = [];
          this.totalCount = 0;
        }

        this.loadQuickDeliveries();
      })
  }

  loadRecommendedProducts() {
    let categoryId = 8;

    this.shoppingService.paging(this.paginationModel.pageNumber, this.paginationModel.pageSize, categoryId, this.userId, this.searchTerm)
      .subscribe(result => {
        if (result.isSuccess) {
          if (result.data) {
            if (result.data.items) {
              result.data.items.forEach(item => {
                item.fileResult.fileContents = "data:" + item.fileResult.contentType + ";base64," + item.fileResult.fileContents;

                item.starsStatus = [];
                for (let i = 1; i <= 5; i++) {
                  if (i <= Math.floor(item.rating!)) {
                    item.starsStatus?.push("checked");
                  }
                  else {
                    item.starsStatus?.push("");
                  }
                }
              })
              this.recommendedProducts = result.data.items;
              this.totalCount = result.data.totalCount;
            }
            else {
              this.recommendedProducts = [];
              this.totalCount = 0;
            }
          }
          else {
            this.recommendedProducts = [];
            this.totalCount = 0;
          }
        }
        else {
          this.recommendedProducts = [];
          this.totalCount = 0;
        }

        this.loadBestVendors();
      })
  }

  loadQuickDeliveries() {
    let categoryId = 9;

    this.shoppingService.paging(this.paginationModel.pageNumber, this.paginationModel.pageSize, categoryId, this.userId, this.searchTerm)
      .subscribe(result => {
        if (result.isSuccess) {
          if (result.data) {
            if (result.data.items) {
              result.data.items.forEach(item => {
                item.fileResult.fileContents = "data:" + item.fileResult.contentType + ";base64," + item.fileResult.fileContents;

                item.starsStatus = [];
                for (let i = 1; i <= 5; i++) {
                  if (i <= Math.floor(item.rating!)) {
                    item.starsStatus?.push("checked");
                  }
                  else {
                    item.starsStatus?.push("");
                  }
                }
              })
              this.quickDeliveries = result.data.items;
              this.totalCount = result.data.totalCount;
            }
            else {
              this.quickDeliveries = [];
              this.totalCount = 0;
            }
          }
          else {
            this.quickDeliveries = [];
            this.totalCount = 0;
          }
        }
        else {
          this.quickDeliveries = [];
          this.totalCount = 0;
        }
      })
  }

  loadVegetables() {
    let categoryId = 1;

    this.shoppingService.paging(this.paginationModel.pageNumber, this.paginationModel.pageSize, categoryId, this.userId, this.searchTerm)
      .subscribe(result => {
        if (result.isSuccess) {
          if (result.data) {
            if (result.data.items) {
              result.data.items.forEach(item => {
                item.fileResult.fileContents = "data:" + item.fileResult.contentType + ";base64," + item.fileResult.fileContents;

                item.starsStatus = [];
                for (let i = 1; i <= 5; i++) {
                  if (i <= Math.floor(item.rating!)) {
                    item.starsStatus?.push("checked");
                  }
                  else {
                    item.starsStatus?.push("");
                  }
                }
              })
              this.vegetables = result.data.items;
              this.totalCount = result.data.totalCount;
            }
            else {
              this.vegetables = [];
              this.totalCount = 0;
            }
          }
          else {
            this.vegetables = [];
            this.totalCount = 0;
          }
        }
        else {
          this.vegetables = [];
          this.totalCount = 0;
        }
      })
  }

  loadDriedFruits() {
    let categoryId = 3;

    this.shoppingService.paging(this.paginationModel.pageNumber, this.paginationModel.pageSize, categoryId, this.userId, this.searchTerm)
      .subscribe(result => {
        if (result.isSuccess) {
          if (result.data) {
            if (result.data.items) {
              result.data.items.forEach(item => {
                item.fileResult.fileContents = "data:" + item.fileResult.contentType + ";base64," + item.fileResult.fileContents;

                item.starsStatus = [];
                for (let i = 1; i <= 5; i++) {
                  if (i <= Math.floor(item.rating!)) {
                    item.starsStatus?.push("checked");
                  }
                  else {
                    item.starsStatus?.push("");
                  }
                }
              })
              this.driedFruits = result.data.items;
              this.totalCount = result.data.totalCount;
            }
            else {
              this.driedFruits = [];
              this.totalCount = 0;
            }
          }
          else {
            this.driedFruits = [];
            this.totalCount = 0;
          }
        }
        else {
          this.driedFruits = [];
          this.totalCount = 0;
        }
      })
  }

  loadFruits() {
    let categoryId = 2;

    this.shoppingService.paging(this.paginationModel.pageNumber, this.paginationModel.pageSize, categoryId, this.userId, this.searchTerm)
      .subscribe(result => {
        if (result.isSuccess) {
          if (result.data) {
            if (result.data.items) {
              result.data.items.forEach(item => {
                item.fileResult.fileContents = "data:" + item.fileResult.contentType + ";base64," + item.fileResult.fileContents;

                item.starsStatus = [];
                for (let i = 1; i <= 5; i++) {
                  if (i <= Math.floor(item.rating!)) {
                    item.starsStatus?.push("checked");
                  }
                  else {
                    item.starsStatus?.push("");
                  }
                }
              })
              this.fruits = result.data.items;
              this.totalCount = result.data.totalCount;
            }
            else {
              this.fruits = [];
              this.totalCount = 0;
            }
          }
          else {
            this.fruits = [];
            this.totalCount = 0;
          }
        }
        else {
          this.fruits = [];
          this.totalCount = 0;
        }
      })
  }

  loadAdvantageousFruits() {
    let categoryId = 6;

    this.shoppingService.paging(this.paginationModel.pageNumber, this.paginationModel.pageSize, categoryId, this.userId, this.searchTerm)
      .subscribe(result => {
        if (result.isSuccess) {
          if (result.data) {
            if (result.data.items) {
              result.data.items.forEach(item => {
                item.fileResult.fileContents = "data:" + item.fileResult.contentType + ";base64," + item.fileResult.fileContents;

                item.starsStatus = [];
                for (let i = 1; i <= 5; i++) {
                  if (i <= Math.floor(item.rating!)) {
                    item.starsStatus?.push("checked");
                  }
                  else {
                    item.starsStatus?.push("");
                  }
                }
              })
              this.advantageous = result.data.items;
              this.totalCount = result.data.totalCount;
            }
            else {
              this.advantageous = [];
              this.totalCount = 0;
            }
          }
          else {
            this.advantageous = [];
            this.totalCount = 0;
          }
        }
        else {
          this.advantageous = [];
          this.totalCount = 0;
        }
      })
  }

  loadHighScores() {
    let categoryId = 5;

    this.shoppingService.paging(this.paginationModel.pageNumber, this.paginationModel.pageSize, categoryId, this.userId, this.searchTerm)
      .subscribe(result => {
        if (result.isSuccess) {
          if (result.data) {
            if (result.data.items) {
              result.data.items.forEach(item => {
                item.fileResult.fileContents = "data:" + item.fileResult.contentType + ";base64," + item.fileResult.fileContents;

                item.starsStatus = [];
                for (let i = 1; i <= 5; i++) {
                  if (i <= Math.floor(item.rating!)) {
                    item.starsStatus?.push("checked");
                  }
                  else {
                    item.starsStatus?.push("");
                  }
                }
              })
              this.highScores = result.data.items;
              this.totalCount = result.data.totalCount;
            }
            else {
              this.highScores = [];
              this.totalCount = 0;
            }
          }
          else {
            this.highScores = [];
            this.totalCount = 0;
          }
        }
        else {
          this.highScores = [];
          this.totalCount = 0;
        }
      })
  }

  ngOnInit(): void {
    this.headerContainerCssClasses = this.layout.getStringCSSClasses('headerContainer');

    this.getUserId();
    this.paginationModel = { pageNumber: 1, pageSize: 10 } as PaginationModel;
    this.loadVegetables();
    this.loadFruits();
    this.loadDriedFruits();
    this.loadAdvantageousFruits();
    this.loadHighScores();
    this.loadRecommendedProducts();
  }

  ngOnDestroy() {
  }

  onSearch() {
    if (this.searchTerm === this.lastSearchTerm) {
      return;
    }
    
    this.lastSearchTerm = this.searchTerm;
    this.loadVegetables();
    this.loadFruits();
    this.loadDriedFruits();
    this.loadAdvantageousFruits();
    this.loadHighScores();
    this.loadRecommendedProducts();
  }

}
