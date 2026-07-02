import { Component, OnDestroy, OnInit, ViewChild, Output, EventEmitter, ElementRef } from '@angular/core';
import { TranslateService } from '@ngx-translate/core';
import { forkJoin } from 'rxjs';
import { ModalComponent, ModalConfig } from "src/app/_metronic/partials";
import { AlertService } from 'src/app/_metronic/partials/layout/alert/alert.service';
import { AuthService } from 'src/app/modules/auth';
import { ProductCommentModel } from 'src/app/modules/product-management/models/comment.model';
import { ProductManagementService } from 'src/app/modules/product-management/product-management.service';

@Component({
  selector: 'app-product-comment',
  templateUrl: './comment.component.html',
  styleUrls: ['./comment.component.scss'],
})
export class CommentComponent implements OnInit, OnDestroy {

  @ViewChild('modal') private modalComponent: ModalComponent;
  @Output() isSuccess: EventEmitter<boolean> = new EventEmitter<boolean>();

  modalConfig: ModalConfig;
  productId: number;

  qualityStar1: boolean = true;
  qualityStar2: boolean = false;
  qualityStar3: boolean = false;
  qualityStar4: boolean = false;
  qualityStar5: boolean = false;

  deliveryStar1: boolean = true;
  deliveryStar2: boolean = false;
  deliveryStar3: boolean = false;
  deliveryStar4: boolean = false;
  deliveryStar5: boolean = false;

  vendorStar1: boolean = true;
  vendorStar2: boolean = false;
  vendorStar3: boolean = false;
  vendorStar4: boolean = false;
  vendorStar5: boolean = false;

  @ViewChild('commentInput', { static: true })
  commentInput: ElementRef<HTMLTextAreaElement>;

  constructor(
    private productManagementService: ProductManagementService,
    private authService: AuthService,
    private alertService: AlertService,
    private translate: TranslateService
  ) {
  }

  checked(name: string) {
    if (name == 'qualityStar2') {
      if (this.qualityStar1 && !this.qualityStar2) {
        this.qualityStar2 = true;
      }
      else if (this.qualityStar2 && !this.qualityStar3) {
        this.qualityStar2 = false;
      }
    }
    else if (name == 'qualityStar3') {
      if (this.qualityStar2 && !this.qualityStar3) {
        this.qualityStar3 = true;
      }
      else if (this.qualityStar3 && !this.qualityStar4) {
        this.qualityStar3 = false;
      }
    }
    else if (name == 'qualityStar4') {
      if (this.qualityStar3 && !this.qualityStar4) {
        this.qualityStar4 = true;
      }
      else if (this.qualityStar4 && !this.qualityStar5) {
        this.qualityStar4 = false;
      }
    }
    else if (name == 'qualityStar5') {
      if (this.qualityStar4) {
        this.qualityStar5 = !this.qualityStar5;
      }
    }

    if (name == 'deliveryStar2') {
      if (this.deliveryStar1 && !this.deliveryStar2) {
        this.deliveryStar2 = true;
      }
      else if (this.deliveryStar2 && !this.deliveryStar3) {
        this.deliveryStar2 = false;
      }
    }
    else if (name == 'deliveryStar3') {
      if (this.deliveryStar2 && !this.deliveryStar3) {
        this.deliveryStar3 = true;
      }
      else if (this.deliveryStar3 && !this.deliveryStar4) {
        this.deliveryStar3 = false;
      }
    }
    else if (name == 'deliveryStar4') {
      if (this.deliveryStar3 && !this.deliveryStar4) {
        this.deliveryStar4 = true;
      }
      else if (this.deliveryStar4 && !this.deliveryStar5) {
        this.deliveryStar4 = false;
      }
    }
    else if (name == 'deliveryStar5') {
      if (this.deliveryStar4) {
        this.deliveryStar5 = !this.deliveryStar5;
      }
    }

    if (name == 'vendorStar2') {
      if (this.vendorStar1 && !this.vendorStar2) {
        this.vendorStar2 = true;
      }
      else if (this.vendorStar2 && !this.vendorStar3) {
        this.vendorStar2 = false;
      }
    }
    else if (name == 'vendorStar3') {
      if (this.vendorStar2 && !this.vendorStar3) {
        this.vendorStar3 = true;
      }
      else if (this.vendorStar3 && !this.vendorStar4) {
        this.vendorStar3 = false;
      }
    }
    else if (name == 'vendorStar4') {
      if (this.vendorStar3 && !this.vendorStar4) {
        this.vendorStar4 = true;
      }
      else if (this.vendorStar4 && !this.vendorStar5) {
        this.vendorStar4 = false;
      }
    }
    else if (name == 'vendorStar5') {
      if (this.vendorStar4) {
        this.vendorStar5 = !this.vendorStar5;
      }
    }
  }

  ngOnDestroy(): void {
  }

  ngOnInit(): void {

  }

  openModal(productId: number) {

    const keys = ['RATING_AND_COMMENT', 'SUBMIT', 'CANCEL'];

    const translations: any = {};

    const observables = keys.map(key => this.translate.get(key));

    forkJoin(observables).subscribe((results) => {
      keys.forEach((key, index) => {
        translations[key] = results[index]
      })
    })

    this.productId = productId;

    this.modalConfig = {
      modalTitle: translations['RATING_AND_COMMENT'],
      closeButtonLabel: translations['SUBMIT'],
      dismissButtonLabel: translations['CANCEL'],
      onDismiss: this.submit.bind(this),
    };

    this.modalComponent.open();
  }

  submit() {
    const comment = this.commentInput.nativeElement.value;

    var deliveryRating = 1;
    if (this.deliveryStar2) {
      deliveryRating += 1;

      if (this.deliveryStar3) {
        deliveryRating += 1;

        if (this.deliveryStar4) {
          deliveryRating += 1;

          if (this.deliveryStar5) {
            deliveryRating += 1;
          }
        }
      }
    }

    var vendorRating = 1;
    if (this.vendorStar2) {
      vendorRating += 1;

      if (this.vendorStar3) {
        vendorRating += 1;

        if (this.vendorStar4) {
          vendorRating += 1;

          if (this.vendorStar5) {
            vendorRating += 1;
          }
        }
      }
    }

    var qualityRating = 1;
    if (this.qualityStar2) {
      qualityRating += 1;

      if (this.qualityStar3) {
        qualityRating += 1;

        if (this.qualityStar4) {
          qualityRating += 1;

          if (this.qualityStar5) {
            qualityRating += 1;
          }
        }
      }
    }

    var data: ProductCommentModel = {
      id: 0,
      comment: comment,
      deliveryRating: deliveryRating,
      qualityRating: qualityRating,
      vendorRating: vendorRating,
      userId: this.authService.currentUserValue!.id,
      productId: this.productId
    }

    this.productManagementService.addComment(data).subscribe(result => {
      if (result.isSuccess) {
        this.alertService.createAlert("success", result.message);
        this.isSuccess.emit(true);
      }
      else {
        this.alertService.createAlert("danger", result.message);
      }
    })

    return true;
  }
}
