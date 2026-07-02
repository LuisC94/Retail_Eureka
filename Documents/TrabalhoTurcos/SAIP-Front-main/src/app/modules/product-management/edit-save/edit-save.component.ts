import { Component, EventEmitter, Output, ViewChild } from "@angular/core";
import { ModalComponent, ModalConfig } from "src/app/_metronic/partials";
import { FormBuilder, FormGroup, Validators } from "@angular/forms";
import { ProductManagementService } from "../product-management.service";
import { ProductModel } from "../models/product.model";
import { CategoryModel } from "../models/category.model";
import { AlertService } from "src/app/_metronic/partials/layout/alert/alert.service";
import { TranslateService } from "@ngx-translate/core";
import { forkJoin } from "rxjs";

@Component({
    selector: 'app-product-editsave',
    templateUrl: './edit-save.component.html',
    styleUrls: ['./edit-save.component.scss'],
})
export class ProductEditSaveComponent {

    @ViewChild('modal') private modalComponent: ModalComponent;
    @Output() isSuccess: EventEmitter<boolean> = new EventEmitter<boolean>();

    isUploadError: boolean = false;
    isUploadSuccess: boolean = false;

    modalConfig: ModalConfig;
    form: FormGroup;

    fileResult: any;
    categories: CategoryModel[] = [];

    categoriesTR: CategoryModel[] = [
        { id: 1, name: "Sebze", isDeleted: false },
        { id: 2, name: "Meyve", isDeleted: false },
        { id: 3, name: "Kuru Meyve", isDeleted: false }
    ];

    categoriesEN: CategoryModel[] = [
        { id: 1, name: "Vegetables", isDeleted: false },
        { id: 2, name: "Fruits", isDeleted: false },
        { id: 3, name: "Dried Fruits", isDeleted: false }
    ];

    constructor(
        private fb: FormBuilder, 
        private productManagementService: ProductManagementService, 
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
            categoryId: [
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
            price: [
                undefined,
                Validators.compose([
                    Validators.required,
                ]),
            ],
            sale: [
                undefined,
            ],
            discountedPrice: [
                undefined,
            ],
            brand: [
                undefined,
            ],
            fileId: [
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
            stock: [
                undefined,
                Validators.compose([
                    Validators.required,
                ]),
            ],
            description: [
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
            this.updateCategoryList();
        });

        this.updateCategoryList();
    }

    updateCategoryList(): void {
        this.translate.get('LANG').subscribe((translation: string) => {
            if (translation === 'tr') {
                this.categories = this.categoriesTR;
            } else {
                this.categories = this.categoriesEN;
            }
        });
    }

    ngAfterViewInit() {
        this.form.get('price')?.valueChanges.subscribe(value => {
            if (this.form.get('sale')?.value == 0 || this.form.get('sale')?.value == '', this.form.get('sale')?.value == null) {
                this.form.get('discountedPrice')?.setValue(value);
            }
            else {
                let sale = this.form.get('sale')?.value;
                let discountedPrice = value - ((value * sale) / 100)
                this.form.get('discountedPrice')?.setValue(discountedPrice);
            }
        })

        this.form.get('sale')?.valueChanges.subscribe(value => {
            if (!(this.form.get('price')?.value == 0 || this.form.get('price')?.value == '', this.form.get('price')?.value == null)) {
                let price = this.form.get('price')?.value;
                let discountedPrice = price - ((price * value) / 100)
                this.form.get('discountedPrice')?.setValue(discountedPrice);
            }
            else {
                this.form.get('discountedPrice')?.setValue(0);
            }
        })
    }

    onFileChange(event: any) {

        if (event.target.files.length > 0) {
            let file: File = event.target.files[0];
            var src = URL.createObjectURL(file);
            var img = new Image;
            img.src = src;

            let width = 0;
            let height = 0;

            img.onload = () => { 
                width = img.naturalWidth; 
                height = img.naturalHeight; 

                if(width == 330 && height == 330) {
                    this.fileResult = { fileContents: src };
                    
                    let formData = new FormData();
                    formData.append("file", file);

                    this.productManagementService.upload(formData).subscribe(result => {
                        if(result.isSuccess) {
                            this.isUploadSuccess = true;

                            setTimeout(() => {
                                this.isUploadSuccess = false;
                            }, 2500);

                            this.form.get("fileId")?.setValue(result.data.id);
                        }
                        else{
                            this.alertService.createAlert("danger", result.message);
                        }
                    })
                }
                else{
                    this.isUploadError = true;

                    setTimeout(() => {
                        this.isUploadError = false;
                      }, 2500);
                }
            }; 
        }        
    }
    
    uploadErrorDialogClose() {
        this.isUploadError = false;
    }

    uploadSuccessDialogClose() {
        this.isUploadSuccess = false;
    }

    openModal(userId: number, productId?: number) {

        const keys = ['NEW_RECORD', 'EDIT', 'SUBMIT', 'CANCEL'];

        const translations: any = {};

        const observables = keys.map(key => this.translate.get(key));

        forkJoin(observables).subscribe((results) => {
            keys.forEach((key, index) => {
                translations[key] = results[index]
            })
        })

        this.modalConfig = {
            modalTitle: productId == null ? translations['NEW_RECORD'] : translations['EDIT'],
            dismissButtonLabel: translations['SUBMIT'],
            onDismiss: this.submit.bind(this),
            shouldDismiss: this.disableSubmitButton.bind(this),
            closeButtonLabel: translations['CANCEL']
        };

        this.form.get('discountedPrice')?.disable();

        if (productId) {
            this.productManagementService.getById(productId).subscribe(result => {
                if (result.isSuccess) {
                    result.data.fileResult.fileContents = "data:" + result.data.fileResult.contentType + ";base64," + result.data.fileResult.fileContents;
                    this.fileResult = result.data.fileResult;

                    if (result.data.sale == null) {
                        result.data.sale = 0;
                        result.data.discountedPrice = result.data.price;
                    }
                    this.form.patchValue(result.data);
                    this.modalComponent.open();
                }
            })
        }
        else {
            this.fileResult = undefined;

            this.form.reset({ id: 0, categoryId: undefined, name: "", price: undefined, sale: undefined, discountedPrice: undefined, brand: "", description: "", stock: undefined, fileId: undefined, userId: userId, isDeleted: false });
            this.modalComponent.open();
        }
    }

    submit() {
        if (this.form.valid) {
            var data = this.form.getRawValue() as ProductModel;
            data.fileResult = null;
            data.sale = (data.sale == undefined || data.sale == null) ? 0 : data.sale;
            if (data.id == 0) {
                this.productManagementService.save(data).subscribe(result => {
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
                this.productManagementService.edit(data).subscribe(result => {
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