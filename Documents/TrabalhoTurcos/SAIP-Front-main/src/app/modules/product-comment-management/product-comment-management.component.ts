import { Component, Inject, LOCALE_ID, OnDestroy, OnInit } from '@angular/core';
import { PaginationModel } from 'src/app/models/pagination.model';
import { ProductManagementService } from '../product-management/product-management.service';
import { ActivatedRoute } from '@angular/router';
import { ProductCommentModel } from '../product-management/models/comment.model';
import { formatDate } from '@angular/common';

@Component({
  selector: 'app-product-comment-management',
  templateUrl: './product-comment-management.component.html',
  styleUrls: ['./product-comment-management.component.scss'],
})
export class ProductCommentManagementComponent implements OnInit, OnDestroy {

  header: string = "Yorumlar";
  totalCount: number;
  paginationModel: PaginationModel;
  productId: number;
  comments: ProductCommentModel[];

  constructor(private productManagementService: ProductManagementService,
    private route: ActivatedRoute,
    @Inject(LOCALE_ID) public locale: string
  ) {
  }

  loadData() {
    this.productManagementService.commentPaging(this.paginationModel.pageNumber, this.paginationModel.pageSize, this.productId)
          .subscribe(result => {
            if(result.isSuccess) {

              result.data.items.forEach(item => {
                item.product!.fileResult.fileContents = "data:" + item.product!.fileResult.contentType + ";base64," + item.product!.fileResult.fileContents;
              
                item.product!.starsStatus = [];
                  for(let i = 1; i <= 5; i++) {
                    if(i <= Math.floor(item.product!.rating!)) {
                      item.product!.starsStatus?.push("checked");
                    }
                    else{
                      item.product!.starsStatus?.push("");
                    }
                  }

                  item.deliveryStars = [];
                  for(let i = 1; i <= 5; i++) {
                    if(i <= Math.floor(item.deliveryRating)) {
                      item.deliveryStars.push("checked");
                    }
                    else{
                      item.deliveryStars.push("");
                    }
                  }

                  item.qualityStars = [];
                  for(let i = 1; i <= 5; i++) {
                    if(i <= Math.floor(item.qualityRating)) {
                      item.qualityStars.push("checked");
                    }
                    else{
                      item.qualityStars.push("");
                    }
                  }

                  item.vendorStars = [];
                  for(let i = 1; i <= 5; i++) {
                    if(i <= Math.floor(item.vendorRating)) {
                      item.vendorStars.push("checked");
                    }
                    else{
                      item.vendorStars.push("");
                    }
                  }

                  item.date = formatDate(item.date!, "dd/MM/yyyy HH:mm", this.locale);

              })

              this.comments = result.data.items;
              this.totalCount = result.data.totalCount;
              
            }
            else{
              this.comments = [];
              this.totalCount = 0;
            }
          })
  }

  ngOnInit(): void {
    this.productId = parseInt(this.route.snapshot.paramMap.get('id')!);

    this.paginationModel = { pageNumber: 1, pageSize: 10 } as PaginationModel;
    this.loadData();
  }

  ngOnDestroy() {
    
  }

  paginationModelChange() {
    this.loadData();
  }
}
