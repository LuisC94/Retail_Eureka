import { Component, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { PaginationModel } from 'src/app/models/pagination.model';
import { BasketService } from 'src/app/_metronic/partials/layout/basket/basket.service';
import { LayoutService } from 'src/app/_metronic/layout/core/layout.service';
import { LayoutInitService } from 'src/app/_metronic/layout/core/layout-init.service';
import { ShoppingService } from '../shopping.service';
import { AuthService } from '../../auth';
import { BasketManagementService } from '../../basket-management/basket-management.service';
import { ProductModel } from '../models/product.model';

@Component({
  selector: 'app-shopping-all',
  templateUrl: './all-products.component.html',
  styleUrls: ['./all-products.component.scss'],
})
export class ShoppingAllProductsComponent implements OnInit, OnDestroy {

  headerContainerCssClasses: string;
  userId: number = 0;
  searchTerm: string = '';
  lastSearchTerm: string = '';

  constructor(private shoppingService: ShoppingService, private authService: AuthService, private basketService: BasketService,
    private layout: LayoutService, private initService: LayoutInitService, private basketManagementService: BasketManagementService

  ) {
    this.initService.init();
  }

  dataSource: ProductModel[];
  totalCount: number;
  paginationModel: PaginationModel;

  getUserId() {
    this.authService.currentUserSubject.asObservable().subscribe(result => {
      if (result) {
        this.userId = result.id;
      }
    });
  }

  loadData() {
    this.shoppingService.paging(this.paginationModel.pageNumber, this.paginationModel.pageSize, 0, this.userId, this.searchTerm)
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
              this.dataSource = result.data.items;
              this.totalCount = result.data.totalCount;
            }
            else {
              this.dataSource = [];
              this.totalCount = 0;
            }
          }
          else {
            this.dataSource = [];
            this.totalCount = 0;
          }
        }
        else {
          this.dataSource = [];
          this.totalCount = 0;
        }
      })
  }

  ngOnInit(): void {
    this.headerContainerCssClasses = this.layout.getStringCSSClasses('headerContainer');

    this.getUserId();
    this.paginationModel = { pageNumber: 1, pageSize: 10 } as PaginationModel;
    this.loadData();
  }

  ngOnDestroy() {
  }

  paginationModelChange(event: PaginationModel) {
    this.paginationModel = event;
    this.loadData();
  }
  
  onSearch() {
    if (this.searchTerm === this.lastSearchTerm) {
      return;
    }
    
    this.lastSearchTerm = this.searchTerm;
    this.loadData();
  }

}
