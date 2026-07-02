import { Component, EventEmitter, OnInit, Output, ViewChild } from "@angular/core";
import { ModalComponent, ModalConfig } from "src/app/_metronic/partials";
import { ComingOrderManagementService } from "../../coming-order-management.service";
import { OrderProductModel } from "../../models/orderproduct.model";
import { ConfirmationComponent } from "src/app/modules/confirmation/confirmation.component";
import { TranslateService } from "@ngx-translate/core";
import { AlertService } from "src/app/_metronic/partials/layout/alert/alert.service";
import { forkJoin } from "rxjs";

@Component({
    selector: 'app-orderinvoice-edit',
    templateUrl: './invoice.component.html',
    styleUrls: ['./invoice.component.scss'],
})
export class InvoiceComponent implements OnInit {

    @ViewChild('deleteConfirmationComponent') private deleteConfirmationComponent: ConfirmationComponent;
    @ViewChild('modal') private modalComponent: ModalComponent;
    @Output() isSuccess: EventEmitter<boolean> = new EventEmitter<boolean>();
    
    modalConfig: ModalConfig;
    fileName?: string;
    fileId: number;
    pdfSrc: any;

    orderProduct: OrderProductModel;

    constructor(
        private comingOrderManagementService: ComingOrderManagementService,
        private translate: TranslateService,
        private alertService: AlertService
    ) {}

    delete(event: number) {
        this.comingOrderManagementService.deleteInvoice(this.orderProduct.id).subscribe(result => {
            if(result.isSuccess) {
                this.fileName = undefined;
                this.pdfSrc = undefined;
                this.orderProduct = result.data;
                this.alertService.createAlert("success", result.message);
            }
            else{
                this.alertService.createAlert("danger", result.message);
            }
        })
    }

    ngAfterViewInit(): void {
        
    }

    ngOnInit(): void {
    }
    
    onFileChange(event: any) {

        if (event.target.files.length > 0) {
            let file = event.target.files[0];
            this.fileName = file.name;
            this.pdfSrc = URL.createObjectURL(file);
            
            let formData = new FormData();
            formData.append("file", file);

            this.comingOrderManagementService.upload(formData).subscribe(result => {
                if(result.isSuccess) {
                    this.orderProduct.fileId = result.data.id;
                    this.orderProduct.product = undefined;

                    this.comingOrderManagementService.addInvoice(this.orderProduct).subscribe(result => {
                        if(result.isSuccess) {
                            this.alertService.createAlert("success", result.message);
                        }
                        else{
                            this.alertService.createAlert("danger", result.message);
                        }
                    });
                }
                else{
                    this.alertService.createAlert("danger", result.message);
                }
            })
        }        
    }

    openDeleteModal() {
        var deleteText = "";
        this.translate.get('DELETE').subscribe((translation)=> {
            deleteText = translation
        })
        this.deleteConfirmationComponent.openModal(deleteText, this.orderProduct.id);
    }


    openModal(orderProduct: OrderProductModel) {

        const keys = ['INVOICE', 'CLOSE'];

        const translations: any = {};

        const observables = keys.map(key => this.translate.get(key));

        forkJoin(observables).subscribe((results) => {
            keys.forEach((key, index) => {
                translations[key] = results[index]
            })
        })

        this.orderProduct = orderProduct;

        this.modalConfig = {
            modalTitle: translations['INVOICE'],
            closeButtonLabel: translations['CLOSE'],
            hideCloseButton() {
                return false;
            },
            hideDismissButton() {
                return true;
            },
        };

        if(this.orderProduct.fileResult) {
            if(!this.orderProduct.fileResult.fileContents.includes("data:" + this.orderProduct.fileResult.contentType + ";base64,"))
            {
                this.orderProduct.fileResult.fileContents = "data:" + this.orderProduct.fileResult.contentType + ";base64," + this.orderProduct.fileResult.fileContents;
            }

            this.pdfSrc = this.orderProduct.fileResult.fileContents;
            this.fileName = this.orderProduct.fileName!;
        }
        
        this.modalComponent.open();
    }
}