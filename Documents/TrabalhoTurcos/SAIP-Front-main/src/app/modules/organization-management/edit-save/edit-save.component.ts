import { Component, EventEmitter, OnInit, Output, ViewChild } from "@angular/core";
import { FormBuilder, FormGroup, Validators } from "@angular/forms";
import { ModalComponent, ModalConfig } from "src/app/_metronic/partials";
import { OrganizationManagementService } from "../organization-management.service";
import { OrganizationModel } from "../models/organization.model";
import { AlertService } from "src/app/_metronic/partials/layout/alert/alert.service";
import { TranslateService } from "@ngx-translate/core";
import { forkJoin } from "rxjs";

@Component({
    selector: 'app-organization-editsave',
    templateUrl: './edit-save.component.html',
    styleUrls: ['./edit-save.component.scss'],
})
export class OrganizationEditSaveComponent implements OnInit{

    @ViewChild('modal') private modalComponent: ModalComponent;
    @Output() isSuccess: EventEmitter<boolean> = new EventEmitter<boolean>();
    
    modalConfig: ModalConfig;
    form: FormGroup;
    organizations: OrganizationModel[] = [];

    constructor(
        private fb: FormBuilder, 
        private organizationManagementService: OrganizationManagementService,
        private alertService: AlertService,
        private translate: TranslateService
    ) {}

    disableSubmitButton() : boolean {
        return this.form.valid;
    }

    get f() {
        return this.form.controls;
    }

    initForm() {
        this.form = this.fb.group({
            id: 0,
            name: [
                "",
                Validators.compose([
                    Validators.required,
                ]),
            ],
            parentId: [
                null
            ],
            isDeleted: false,
        });
    }

    ngOnInit(): void {
        this.initForm();
    }
    
    openModal(organizationId?: number) {

        this.organizationManagementService.all().subscribe(result => {
            if(result.isSuccess) {
                this.organizations = result.data;
            }
        })

        const keys = ['NEW_RECORD', 'EDIT', 'SUBMIT', 'CANCEL'];

        const translations: any = {};

        const observables = keys.map(key => this.translate.get(key));

        forkJoin(observables).subscribe((results) => {
            keys.forEach((key, index) => {
                translations[key] = results[index]
            })
        })

        this.modalConfig = {
            modalTitle: organizationId == null ? translations['NEW_RECORD'] : translations['EDIT'],
            dismissButtonLabel: translations['SUBMIT'],
            onDismiss: this.submit.bind(this),
            shouldDismiss: this.disableSubmitButton.bind(this),
            closeButtonLabel: translations['CANCEL']
        };

        if (organizationId) {
            this.organizationManagementService.getById(organizationId).subscribe(result => {
                if(result.isSuccess) {
                    this.form.patchValue(result.data);
                    this.modalComponent.open();
                }
            })
        }
        else{
            this.form.reset({id : 0, name: "", parentId: null, isDeleted: false});
            this.modalComponent.open();
        }
    }

    submit() {
        if(this.form.valid) {
            var data = this.form.getRawValue() as OrganizationModel;

            if(!(data.parentId! > 0)) {
                data.parentId = undefined;
            }
            
            if(data.id == 0) {
                this.organizationManagementService.save(data).subscribe(result => {
                    if(result.isSuccess) {
                        this.alertService.createAlert("success", result.message);
                        this.isSuccess.emit(true);
                    }
                    else{
                        this.alertService.createAlert("danger", result.message);
                    }
                })
            }
            else{
                this.organizationManagementService.edit(data).subscribe(result => {
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