import { Component, EventEmitter, Output, ViewChild } from "@angular/core";
import { FormBuilder, FormGroup, Validators } from "@angular/forms";
import { ModalComponent, ModalConfig } from "src/app/_metronic/partials";
import { UserManagementService } from "../../user-management.service";
import { RoleModel } from "../../models/role.model";
import { PermissionModel } from "../../models/permission.model";
import { AlertService } from "src/app/_metronic/partials/layout/alert/alert.service";
import { forkJoin } from "rxjs";
import { TranslateService } from "@ngx-translate/core";

@Component({
    selector: 'app-role-editsave',
    templateUrl: './edit-save.component.html',
    styleUrls: ['./edit-save.component.scss'],
})
export class RoleEditSaveComponent {

    @ViewChild('modal') private modalComponent: ModalComponent;
    @Output() isSuccess: EventEmitter<boolean> = new EventEmitter<boolean>();

    modalConfig: ModalConfig;
    form: FormGroup;
    permissionList: PermissionModel[];

    constructor(
        private fb: FormBuilder, 
        private userManagementService: UserManagementService,
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
            permissions: [
                null,
                Validators.compose([
                    Validators.required,
                ]),
            ],
            isDeleted: false,
            isSystemData: false
        });
    }

    ngOnInit(): void {
        this.initForm();
    }

    openModal(roleId?: number) {

        this.userManagementService.allPermissions().subscribe(result => {
            if(result.isSuccess) {
                this.permissionList = result.data;
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
            modalTitle: roleId == null ? translations['NEW_RECORD'] : translations['EDIT'],
            dismissButtonLabel: translations['SUBMIT'],
            onDismiss: this.submit.bind(this),
            shouldDismiss: this.disableSubmitButton.bind(this),
            closeButtonLabel: translations['CANCEL']
        };

        if (roleId) {
            this.userManagementService.getRoleById(roleId).subscribe(result => {
                if(result.isSuccess) {
                    this.form.patchValue(result.data);
                    this.modalComponent.open();
                }
            })
        }
        else{
            this.form.reset({id : 0, name: "", permissions: null, isDeleted: false, isSystemData: false});
            this.modalComponent.open();
        }
    }

    submit() {
        if(this.form.valid) {
            var data = this.form.getRawValue() as RoleModel;

            if(data.id == 0) {
                this.userManagementService.roleSave(data).subscribe(result => {
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
                this.userManagementService.roleEdit(data).subscribe(result => {
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