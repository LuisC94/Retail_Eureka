import { Component, OnDestroy, OnInit, LOCALE_ID, Inject, ViewChild } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { formatDate } from '@angular/common';
import { OrderStatusEnum } from 'src/app/enums/permission.enum';
import { BasketModel } from '../../shopping/models/basket.model';
import { OrderManagementService } from '../order-management.service';
import { OrderModel } from '../models/order.model';
import { InvoiceComponent } from './invoice/invoice.component';
import { CommentComponent } from './comment/comment.component';
import { TranslateService } from '@ngx-translate/core';
import { forkJoin } from 'rxjs';

@Component({
  selector: 'app-order-detail',
  templateUrl: './order-detail.component.html',
  styleUrls: ['./order-detail.component.scss'],
})
export class OrderDetailComponent implements OnInit, OnDestroy {

  @ViewChild('invoiceComponent') private invoiceComponent: InvoiceComponent;
  @ViewChild('commentComponent') private commentComponent: CommentComponent;

  header: string = "Sipariş Detay";
  basket: BasketModel[] = [];
  basketFromStorage: BasketModel[] = [];
  numberOfItem: number = 0;
  totalPrice: number = 0;
  orderId: number;
  order: OrderModel;
  private langChangeSubscription: any;

  constructor(
    private orderManagementService: OrderManagementService, 
    private translate: TranslateService, 
    private route: ActivatedRoute, 
    @Inject(LOCALE_ID) public locale: string
  ) {
  }

  addDays(date: string, days: number) {
    var result = new Date(date);
    result.setDate(result.getDate() + days);
    return result;
  }

  ngOnDestroy(): void {
    if (this.langChangeSubscription) {
      this.langChangeSubscription.unsubscribe();
    }
  }

  getById() {
    const keys = ['ORDER_COMPLETED', 'ORDER_NOT_YET_COMPLETED','PENDING_APPROVAL', 'APPROVED', 'PREPARING', 'SHIPPED', 'DELIVERED'];

    const translationRequest = keys.map(key => this.translate.get(key));
    forkJoin(translationRequest).subscribe((translations)=>{
      const [orderCompleted, orderNotYetCompleted,pendingApprovalText, approvedText, preparingText, shippedText, deliveredText] = translations;

      this.orderManagementService.getById(this.orderId).subscribe(result => {
        if (result.isSuccess) {
          result.data.orderDate = formatDate(result.data.orderDate!, "dd/MM/yyyy HH:mm", this.locale);
  
          if (result.data.orderStatus == OrderStatusEnum['Sipariş Tamamlandı']) {
            result.data.orderStatusStr = orderCompleted;
          }
          else if (result.data.orderStatus == OrderStatusEnum['Sipariş Tamamlanmadı']) {
            result.data.orderStatusStr = orderNotYetCompleted;
          }
  
          this.order = result.data;
  
          this.order.orderProducts?.forEach(orderProduct => {
            if (orderProduct.orderStatus == OrderStatusEnum['Onay Bekliyor']) {
              orderProduct.orderStatusStr = pendingApprovalText;
            }
            else if (orderProduct.orderStatus == OrderStatusEnum['Onaylandı']) {
              orderProduct.orderStatusStr = approvedText;
            }
            else if (orderProduct.orderStatus == OrderStatusEnum['Hazırlanıyor']) {
              orderProduct.orderStatusStr = preparingText;
            }
            else if (orderProduct.orderStatus == OrderStatusEnum['Kargolandı']) {
              orderProduct.orderStatusStr = shippedText;
            }
            else if (orderProduct.orderStatus == OrderStatusEnum['Teslim Edildi']) {
              orderProduct.orderStatusStr = deliveredText;var today = new Date();
              var controlDate = this.addDays(orderProduct.proccessDate!, 15);
  
              if(today.getTime() <= controlDate.getTime()) {
                orderProduct.canEvaluate = true;
  
                if(orderProduct.product?.commentsCount! > 0) {
                  orderProduct.canEvaluate = false;
                }
              }
              else{
                orderProduct.canEvaluate = false;
              }
            }
  
            orderProduct.proccessDate = formatDate(orderProduct.proccessDate!, "dd/MM/yyyy HH:mm", this.locale);
            var product = orderProduct.product!;
            product.fileResult.fileContents = "data:" + product.fileResult.contentType + ";base64," + product.fileResult.fileContents;
            orderProduct.product = product;
          })
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
    this.orderId = parseInt(this.route.snapshot.paramMap.get('id')!);
    this.getById();
  }

  private updateHeader(): void {
    this.translate.get('ORDER_DETAIL').subscribe((translation: string) => {
      this.header = translation;
    });
  }

  openInvoiceModal(orderProductId: number) {
    var orderProduct = this.order.orderProducts?.filter(f => f.id == orderProductId)[0];
    this.invoiceComponent.openModal(orderProduct!);
  }

  openCommentModal(orderProductId: number) {
    var productId = this.order.orderProducts?.filter(f => f.id == orderProductId)[0].productId;
    this.commentComponent.openModal(productId!);
  }
}
