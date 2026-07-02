import { Component, EventEmitter, OnInit, Output, ViewChild } from "@angular/core";
import { ModalComponent, ModalConfig } from "src/app/_metronic/partials";
import { OrderProductModel } from "../../models/orderproduct.model";
import { TranslateService } from "@ngx-translate/core";
import { forkJoin } from "rxjs";

@Component({
    selector: 'app-orderinvoice-edit',
    templateUrl: './invoice.component.html',
    styleUrls: ['./invoice.component.scss'],
})
export class InvoiceComponent implements OnInit {

    @ViewChild('modal') private modalComponent: ModalComponent;
    @Output() isSuccess: EventEmitter<boolean> = new EventEmitter<boolean>();
    
    modalConfig: ModalConfig;
    fileName: string;
    pdfSrc: any;

    orderProduct: OrderProductModel;

    constructor( 
        private translate: TranslateService
    ) {}

    ngAfterViewInit(): void {
        
    }

    ngOnInit(): void {
    }
    
    openModal(orderProduct: OrderProductModel) {
        const keys = ['INVOICE', 'CLOSE', 'DOWNLOAD'];

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
            dismissButtonLabel: translations['DOWNLOAD'],
            onDismiss: this.downloadFile.bind(this),
        };

        if(!this.orderProduct.fileResult.fileContents.includes("data:" + this.orderProduct.fileResult.contentType + ";base64,"))
        {
            this.orderProduct.fileResult.fileContents = "data:" + this.orderProduct.fileResult.contentType + ";base64," + this.orderProduct.fileResult.fileContents;
        }
        
        this.pdfSrc = this.orderProduct.fileResult.fileContents;
        this.fileName = this.orderProduct.fileName!;
        this.modalComponent.open();
    }

    downloadFile() {
        const downloadLink = document.createElement('a');
        downloadLink.href = this.pdfSrc;
        downloadLink.download = this.fileName;
        downloadLink.click();

        return true;
    }
}