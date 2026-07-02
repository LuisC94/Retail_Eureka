import { AfterViewInit, Component, EventEmitter, OnInit, Output, ViewChild } from "@angular/core";
import { ModalComponent, ModalConfig } from "src/app/_metronic/partials";
import { FormBuilder, FormGroup, Validators } from "@angular/forms";
import { AlertService } from "src/app/_metronic/partials/layout/alert/alert.service";
import { TranslateService } from "@ngx-translate/core";
import { forkJoin } from "rxjs";
import { UserManagementService } from "src/app/modules/user-management/user-management.service";
import { UserAddressModel } from "src/app/modules/user-management/models/user-address.model";

@Component({
    selector: 'app-address-editsave',
    templateUrl: './edit-save.component.html',
    styleUrls: ['./edit-save.component.scss'],
})
export class AddressEditSaveComponent implements OnInit, AfterViewInit{

    @ViewChild('modal') private modalComponent: ModalComponent;
    @Output() isSuccess: EventEmitter<boolean> = new EventEmitter<boolean>();

    modalConfig: ModalConfig;
    form: FormGroup;

    invoiceTypes: any[] = [];
    invoiceTypesTR: any[] = [
        { id: 1, name: "Bireysel", isDeleted: false },
        { id: 2, name: "Kurumsal", isDeleted: false },
    ];
    invoiceTypesEN: any[] = [
        { id: 1, name: "Individual", isDeleted: false },
        { id: 2, name: "Corporate", isDeleted: false },
    ];

    constructor(
        private fb: FormBuilder, 
        private userManagementService: UserManagementService, 
        private translate: TranslateService,
        private alertService: AlertService
    ) { }

    disableSubmitButton(): boolean {
        return this.form.valid;
    }

    get f() {
        return this.form.controls;
    }

    initForm() {
        this.form = this.fb.group({
            id: 0,
            invoiceType: [
                undefined,
                Validators.compose([
                    Validators.required,
                ]),
            ],
            name: [
                "",
                Validators.compose([
                    Validators.required,
                ]),
            ],
            surname: [
                "",
                Validators.compose([
                    Validators.required,
                ]),
            ],
            phone: [
                "",
                Validators.compose([
                    Validators.required,
                ]),
            ],
            country: [
                "",
                Validators.compose([
                    Validators.required,
                ]),
            ],
            city: [
                "",
                Validators.compose([
                    Validators.required,
                ]),
            ],
            addressHeader: [
                "",
                Validators.compose([
                    Validators.required,
                ]),
            ],
            address: [
                "",
                Validators.compose([
                    Validators.required,
                ]),
            ],
            district: [
                undefined,
                Validators.compose([
                    Validators.required,
                ]),
            ],
            userId: [
                undefined,
                Validators.compose([
                    Validators.required,
                ]),
            ],
            vkn: [
                undefined
            ],
            vergiDairesi: [
                undefined
            ],
            firmaAdi: [
                undefined
            ],
            isDeleted: false
        });
    }

    ngOnInit(): void {
        this.initForm();
        this.updateTranslationsAndColumns();
    }

    updateTranslationsAndColumns(): void {
        this.translate.onLangChange.subscribe(() => {
            this.updateInvoiceTypeList();
        });

        this.updateInvoiceTypeList();
    }

    updateInvoiceTypeList(): void {
        this.translate.get('LANG').subscribe((translation: string) => {
            if (translation === 'tr') {
                this.invoiceTypes = this.invoiceTypesTR;
            } else {
                this.invoiceTypes = this.invoiceTypesEN;
            }
        });
    }

    ngAfterViewInit() {
        this.form.get("invoiceType")?.valueChanges.subscribe(value => {
            if(value == 2) {
                this.form.get('vkn')?.setValidators(Validators.compose([
                    Validators.required,
                ])); 
                
                this.form.get('vergiDairesi')?.setValidators(Validators.compose([
                    Validators.required,
                ]));

                this.form.get('firmaAdi')?.setValidators(Validators.compose([
                    Validators.required,
                ]));
            }
            else{
                this.form.get('vkn')?.setValue(undefined);
                this.form.get('vkn')?.clearValidators();
                this.form.get('vkn')?.updateValueAndValidity();

                this.form.get('vergiDairesi')?.setValue(undefined);
                this.form.get('vergiDairesi')?.clearValidators();
                this.form.get('vergiDairesi')?.updateValueAndValidity();

                this.form.get('firmaAdi')?.setValue(undefined);
                this.form.get('firmaAdi')?.clearValidators();
                this.form.get('firmaAdi')?.updateValueAndValidity();
            }
        })
    }

    openModal(userId: number, addressId?: number) {

        const keys = ['NEW_RECORD', 'EDIT', 'SUBMIT', 'CANCEL'];

        const translations: any = {};

        const observables = keys.map(key => this.translate.get(key));

        forkJoin(observables).subscribe((results) => {
            keys.forEach((key, index) => {
                translations[key] = results[index]
            })
        })

        this.modalConfig = {
            modalTitle: addressId == null ? translations['NEW_RECORD'] : translations['EDIT'],
            dismissButtonLabel: translations['SUBMIT'],
            onDismiss: this.submit.bind(this),
            shouldDismiss: this.disableSubmitButton.bind(this),
            closeButtonLabel: translations['CANCEL']
        };


        if (addressId) {
            this.userManagementService.getUserAddressById(addressId).subscribe(result => {
                if (result.isSuccess) {
                    this.form.patchValue(result.data);
                    this.modalComponent.open();
                }
            })
        }
        else {
            this.form.reset({ id: 0, invoiceType: undefined, name: "", surname: "", phone: "", country: "", city: "", district: "", address: "", addressHeader: "", vkn: "", vergiDairesi: "", firmaAdi: "", userId: userId, isDeleted: false });
            this.modalComponent.open();
        }
    }

    submit() {
        if (this.form.valid) {
            var data = this.form.getRawValue() as UserAddressModel;
            if (data.id == 0) {
                this.userManagementService.userAddressSave(data).subscribe(result => {
                    if(result.isSuccess) {
                        this.alertService.createAlert("success", result.message);
                        this.isSuccess.emit(true);
                    }
                    else{
                        this.alertService.createAlert("danger", result.message);
                    }
                })
            }
            else {
                this.userManagementService.userAddressUpdate(data).subscribe(result => {
                    if(result.isSuccess) {
                        this.alertService.createAlert("success", result.message);
                        this.isSuccess.emit(true);
                    }
                    else{
                        this.alertService.createAlert("danger", result.message);
                    }
                })
            }
        }

        return true;
    }
}