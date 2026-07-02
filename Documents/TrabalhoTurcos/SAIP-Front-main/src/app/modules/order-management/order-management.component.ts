import { Component, OnDestroy, OnInit, LOCALE_ID, Inject } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService, UserType } from '../auth';
import { ColumnModel } from 'src/app/models/column-model';
import { OrderModel } from './models/order.model';
import { PaginationModel } from 'src/app/models/pagination.model';
import { OrderManagementService } from './order-management.service';
import { formatDate } from '@angular/common';
import { OrderStatusEnum } from 'src/app/enums/permission.enum';
import { TranslateService } from '@ngx-translate/core';
import { forkJoin } from 'rxjs';

@Component({
  selector: 'app-order-management',
  templateUrl: './order-management.component.html',
  styleUrls: ['./order-management.component.scss'],
})
export class OrderManagementComponent implements OnInit, OnDestroy {

  currentUser: UserType;

  hasEditPermission: boolean = false;
  hasDeletePermission: boolean = false;
  hasNewRecordPermission: boolean = false;
  hasShowPermission: boolean = true;

  searchTerm: string = '';
  lastSearchTerm: string = '';

  tableName: string = "";
  columnList: ColumnModel[] = []
  columnListTR: ColumnModel[] = [
    { name: "Id", index: "id", visibility: false },
    { name: "Sipariş Numarası", index: "orderNo", visibility: true },
    { name: "Tutar", index: "priceStr", visibility: true },
    { name: "Sipariş Tarihi", index: "orderDate", visibility: true },
    { name: "Durum", index: "orderStatusStr", visibility: true },
    {name: "İşlemler", index: null, visibility: true}
  ]
  columnListEN: ColumnModel[] = [
    { name: "Id", index: "id", visibility: false },
    { name: "Order Number", index: "orderNo", visibility: true },
    { name: "Amount", index: "priceStr", visibility: true },
    { name: "Order Date", index: "orderDate", visibility: true },
    { name: "Status", index: "orderStatusStr", visibility: true },
    { name: "Actions", index: null, visibility: true }
  ];

  private langChangeSubscription: any;

  dataSource: OrderModel[];
  totalCount: number;
  paginationModel: PaginationModel;

  constructor(private authService: AuthService, private router: Router, private orderManagementService: OrderManagementService, 
   private translate: TranslateService ,@Inject(LOCALE_ID) public locale: string) {}

  loadData() {
    const keys = ["ORDER_COMPLETED", "ORDER_NOT_YET_COMPLETED"];
    const translationRequest = keys.map(key => this.translate.get(key));

    forkJoin(translationRequest).subscribe((translations) => {
      const[orderCompleted,orderNotYetCompleted] = translations;
      this.orderManagementService.paging(this.paginationModel.pageNumber, this.paginationModel.pageSize, this.currentUser?.id, this.searchTerm)
      .subscribe(result => {
        if (result.isSuccess) {
          result.data.items.forEach(item => {
            item.orderDate = formatDate(item.orderDate!, "dd/MM/yyyy HH:mm", this.locale);

            if (item.orderStatus == OrderStatusEnum['Sipariş Tamamlandı']) {
              item.orderStatusStr = orderCompleted;
            }
            else if (item.orderStatus == OrderStatusEnum['Sipariş Tamamlanmadı']) {
              item.orderStatusStr = orderNotYetCompleted;
            }

            item.priceStr = item.price.toFixed(2) + " ₺";
          })
          this.dataSource = result.data.items;
          this.totalCount = result.data.totalCount;
        }
        else {
          this.dataSource = [];
          this.totalCount = 0;
        }
      })
    })
    
    
  }

  ngOnDestroy(): void {
    if (this.langChangeSubscription) {
      this.langChangeSubscription.unsubscribe();
    }
  }

  ngOnInit(): void {
    const currentUser = this.authService.currentUserValue;
    if (currentUser) {
      this.currentUser = currentUser;
    }

    this.paginationModel = { pageNumber: 1, pageSize: 10 } as PaginationModel;

    this.langChangeSubscription = this.translate.onLangChange.subscribe(() => {
      this.updateTranslationsAndColumns();
      this.loadData();
    });

    this.updateTranslationsAndColumns();
    this.loadData();    
  }

  updateTranslationsAndColumns() {
    this.translate.onLangChange.subscribe(() => {
      this.translate.get('MY_PLACED_ORDERS').subscribe((translation: string) => {
        this.tableName = translation;
      });
    });

    this.translate.get('MY_PLACED_ORDERS').subscribe((translation: string) => {
      this.tableName = translation;
    });


    this.translate.onLangChange.subscribe(() => {
      this.translate.get('LANG').subscribe((translation: string) => {
        if(translation === 'tr') {
          this.columnList = this.columnListTR
        } else {
          this.columnList = this.columnListEN
        }
      });
    });

    this.translate.get('LANG').subscribe((translation: string) => {
      if(translation === 'tr') {
        this.columnList = this.columnListTR
      } else {
        this.columnList = this.columnListEN
      }
    });
  }

  paginationModelChange(event: PaginationModel) {
    this.paginationModel = event;
    this.loadData();
  }

  routeToOrderDetail(event: number) {
    this.router.navigate(['ordermanagement/' + event])
  }

  onSearch() {
    if (this.searchTerm === this.lastSearchTerm) {
      return;
    }
    
    this.lastSearchTerm = this.searchTerm;
    this.loadData();
  }
}
