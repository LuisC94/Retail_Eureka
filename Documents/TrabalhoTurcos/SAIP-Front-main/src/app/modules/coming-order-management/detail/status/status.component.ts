import { Component, EventEmitter, Inject, LOCALE_ID, OnInit, Output, ViewChild } from "@angular/core";
import { ModalComponent, ModalConfig } from "src/app/_metronic/partials";
import { FormBuilder, FormGroup, Validators } from "@angular/forms";
import { ComingOrderManagementService } from "../../coming-order-management.service";
import { OrderProductModel } from "../../models/orderproduct.model";
import { AlertService } from "src/app/_metronic/partials/layout/alert/alert.service";
import { forkJoin } from "rxjs";
import { TranslateService } from "@ngx-translate/core";

@Component({
    selector: 'app-orderstatus-edit',
    templateUrl: './status.component.html',
    styleUrls: ['./status.component.scss'],
})
export class StatusComponent implements OnInit {

    @ViewChild('modal') private modalComponent: ModalComponent;
    @Output() isSuccess: EventEmitter<boolean> = new EventEmitter<boolean>();

    modalConfig: ModalConfig;
    form: FormGroup;

    orderProduct: OrderProductModel;
    status: any[] = [];
   

    constructor(
        private fb: FormBuilder, 
        private comingOrderManagementService: ComingOrderManagementService,
        @Inject(LOCALE_ID) public locale: string,
        private alertService: AlertService,
        private translate: TranslateService
    ) { }

    disableSubmitButton(): boolean {
        return this.form.valid;
    }

    private formatJSDate(date?: string) {
        const d = new Date(date!);
        let month = '' + (d.getMonth() + 1);
        let day = '' + d.getDate();
        const year = d.getFullYear();

        let hour = '' + (d.getHours());
        let minute = '' + (d.getMinutes());

        if (month.length < 2) month = '0' + month;
        if (day.length < 2) day = '0' + day;

        if (hour.length < 2) hour = '0' + hour;
        if (minute.length < 2) minute = '0' + minute;

        var dateStr = [year, month, day].join('-');
        var timeStr = [hour, minute].join(':');

        return dateStr + ' ' + timeStr;
    }

    get f() {
        return this.form.controls;
    }

    initForm() {
        this.form = this.fb.group({
            id: 0,
            productId: undefined,
            orderId: undefined,
            order: undefined,
            orderStatus: [
                undefined,
                Validators.compose([
                    Validators.required,
                ]),
            ],
            proccessDate: [
                undefined,
                Validators.compose([
                    Validators.required,
                ]),
            ],
            trackingNo: null,
            trackingDate: [
                undefined
            ],
            completionDate: [
                undefined
            ],
            vendorId: undefined
        });
    }

    ngAfterViewInit(): void {
        this.form.get('orderStatus')?.valueChanges.subscribe(value => {
            if (value == 3) {
                this.form.get('trackingNo')?.setValidators(Validators.compose([
                    Validators.required,
                ]));

                this.form.get('trackingDate')?.setValidators(Validators.compose([
                    Validators.required,
                ]));
            }
            else if (value == 4) {
                this.form.get('completionDate')?.setValidators(Validators.compose([
                    Validators.required,
                ]));

                this.form.get('trackingNo')?.clearValidators();
                this.form.get('trackingNo')?.updateValueAndValidity();

                this.form.get('trackingDate')?.clearValidators();
                this.form.get('trackingDate')?.updateValueAndValidity();
            }
        })
    }

    ngOnInit(): void {
        this.initForm();
    }

    updateTranslationsAndColumns(statusTr:any, statusEn:any): void {
        this.translate.onLangChange.subscribe(() => {
            this.updateCategoryList(statusTr,statusEn);
        });

        this.updateCategoryList(statusTr,statusEn);
    }

    updateCategoryList(statusTr:any, statusEn:any): void {
        this.translate.get('LANG').subscribe((translation: string) => {
            if (translation === 'tr') {
                this.status = statusTr;
            } else {
                this.status = statusEn;
            }
        });
    }

    openModal(orderProduct: OrderProductModel) {

        const statusTR: any[] = [
            { id: 0, name: "Onay Bekliyor", disabled: false },
            { id: 1, name: "Onaylandı", disabled: false },
            { id: 2, name: "Hazırlanıyor", disabled: false },
            { id: 3, name: "Kargolandı", disabled: false },
            { id: 4, name: "Teslim Edildi", disabled: false }
        ];
        const statusEN: any[] = [
            { id: 0, name: "Pending Approval", disabled: false },
            { id: 1, name: "Approved", disabled: false },
            { id: 2, name: "Preparing", disabled: false },
            { id: 3, name: "Shipped", disabled: false },
            { id: 4, name: "Delivered", disabled: false }
        ];

        const keys = ['EDIT_STATUS', 'SUBMIT', 'CANCEL'];

        const translations: any = {};

        const observables = keys.map(key => this.translate.get(key));

        forkJoin(observables).subscribe((results) => {
            keys.forEach((key, index) => {
                translations[key] = results[index]
            })
        })

        this.updateTranslationsAndColumns(statusTR, statusEN)

        this.orderProduct = orderProduct;
        this.status = this.status.filter(f => f.id == this.orderProduct.orderStatus || f.id == (this.orderProduct.orderStatus!+1));
        
        this.modalConfig = {
            modalTitle: translations['EDIT_STATUS'],
            dismissButtonLabel: translations['SUBMIT'],
            onDismiss: this.submit.bind(this),
            shouldDismiss: this.disableSubmitButton.bind(this),
            closeButtonLabel: translations['CANCEL']
        };

        this.orderProduct.trackingDate = this.orderProduct.trackingDate ? this.formatJSDate(this.orderProduct.trackingDate) : this.orderProduct.trackingDate;
        this.orderProduct.completionDate = this.orderProduct.completionDate ? this.formatJSDate(this.orderProduct.completionDate) : this.orderProduct.completionDate;
        
        setTimeout(() => {
            this.form.patchValue(orderProduct);
            this.modalComponent.open();
        }, 250);
    }

    submit() {
        if (this.form.valid) {
            let data = this.form.getRawValue() as OrderProductModel;

            if (data.orderStatus == 3){
                data.completionDate = undefined;
                data.proccessDate = data.trackingDate;
            }
            else if (data.orderStatus == 4){
                data.trackingDate = this.orderProduct.trackingDate;
                data.proccessDate = data.completionDate;
            }
            else {
                data.proccessDate = undefined;
            }

            data.proccessDate = data.proccessDate ? new Date(data.proccessDate!).toISOString() : data.proccessDate;
            data.trackingDate = data.trackingDate ? new Date(data.trackingDate!).toISOString() : data.trackingDate;
            data.completionDate = data.completionDate ? new Date(data.completionDate!).toISOString() : data.completionDate;

            this.comingOrderManagementService.updateStatus(data).subscribe(result => {
                if (result.isSuccess) {
                    this.alertService.createAlert("success", result.message);
                    this.isSuccess.emit(true);
                }
                else {
                    this.alertService.createAlert("danger", result.message);
                }
            })
        }

        return true;
    }
}