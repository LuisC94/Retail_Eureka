import { Component, OnDestroy, OnInit, LOCALE_ID, Inject, ViewChild } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { formatDate } from '@angular/common';
import { OrderStatusEnum } from 'src/app/enums/permission.enum';
import { ComingOrderManagementService } from '../coming-order-management.service';
import { OrderProductModel } from '../models/orderproduct.model';
import { StatusComponent } from './status/status.component';
import { InvoiceComponent } from './invoice/invoice.component';
import { TranslateService } from '@ngx-translate/core';
import { forkJoin } from 'rxjs';

@Component({
  selector: 'app-coming-order-detail',
  templateUrl: './coming-order-detail.component.html',
  styleUrls: ['./coming-order-detail.component.scss'],
})
export class ComingOrderDetailComponent implements OnInit, OnDestroy {

  @ViewChild('statusComponent') private statusComponent: StatusComponent;
  @ViewChild('invoiceComponent') private invoiceComponent: InvoiceComponent;

  header: string = "SS";
  orderProductId: number;
  orderProduct: OrderProductModel;
  orderProductTemp: OrderProductModel;
  private langChangeSubscription: any;

  constructor(private comingOrderManagementService: ComingOrderManagementService, private translate: TranslateService,
    private route: ActivatedRoute, @Inject(LOCALE_ID) public locale: string) {
  }

  ngOnDestroy(): void {
    if (this.langChangeSubscription) {
      this.langChangeSubscription.unsubscribe();
    }
  }

  getById() {
    const keys = ['PENDING_APPROVAL', 'APPROVED', 'PREPARING', 'SHIPPED', 'DELIVERED'];
    const translationRequest = keys.map(key => this.translate.get(key));

    forkJoin(translationRequest).subscribe((translations) => {
      const [pendingApprovalText, approvedText, preparingText, shippedText, deliveredText] = translations;
      this.comingOrderManagementService.getById(this.orderProductId).subscribe(result => {
        if (result.isSuccess) {
  
          this.orderProductTemp = Object.assign({}, result.data);
          this.orderProduct = result.data;
  
          if (this.orderProduct.orderStatus == OrderStatusEnum['Onay Bekliyor']) {
            this.orderProduct.orderStatusStr = pendingApprovalText;
          }
          else if (this.orderProduct.orderStatus == OrderStatusEnum['Onaylandı']) {
            this.orderProduct.orderStatusStr = approvedText;
          }
          else if (this.orderProduct.orderStatus == OrderStatusEnum['Hazırlanıyor']) {
            this.orderProduct.orderStatusStr = preparingText;
          }
          else if (this.orderProduct.orderStatus == OrderStatusEnum['Kargolandı']) {
            this.orderProduct.orderStatusStr = shippedText;
          }
          else if (this.orderProduct.orderStatus == OrderStatusEnum['Teslim Edildi']) {
            this.orderProduct.orderStatusStr = deliveredText;
          }
  
          this.orderProduct.orderDate = formatDate(this.orderProduct.order?.orderDate!, "dd/MM/yyyy HH:mm", this.locale);
          this.orderProduct.proccessDate = formatDate(this.orderProduct.proccessDate!, "dd/MM/yyyy HH:mm", this.locale);
  
          var product = this.orderProduct.product!;
          product.fileResult.fileContents = "data:" + product.fileResult.contentType + ";base64," + product.fileResult.fileContents;
          this.orderProduct.product = product;
        }
      })
    })
  }

  isSuccess(event: boolean) {
    this.getById();
  }

  ngOnInit(): void {
    this.langChangeSubscription = this.translate.onLangChange.subscribe(() => {
      this.updateHeader();
      this.getById();
    });

    this.updateHeader(); 
    this.orderProductId = parseInt(this.route.snapshot.paramMap.get('id')!);
    this.getById();
  }

  updateHeader(){
    this.translate.onLangChange.subscribe(() => {
      this.translate.get('ORDER_DETAIL').subscribe((translation: string) => {
        this.header = translation;
      });
    });

    this.translate.get('ORDER_DETAIL').subscribe((translation: string) => {
      this.header = translation;
    });
  }

  openEditModal() {
    this.statusComponent.openModal(this.orderProductTemp);
  }

  openInvoiceModal() {
    this.invoiceComponent.openModal(this.orderProductTemp);
  }
}
