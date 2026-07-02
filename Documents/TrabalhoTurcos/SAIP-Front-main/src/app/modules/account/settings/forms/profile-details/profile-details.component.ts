import { ChangeDetectorRef, Component, Input, OnChanges, OnDestroy, OnInit, SimpleChanges, ViewChild } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { BehaviorSubject, Subscription } from 'rxjs';
import { AlertService } from 'src/app/_metronic/partials/layout/alert/alert.service';
import { UserType } from 'src/app/modules/auth';
import { UserModel } from 'src/app/modules/user-management/models/user.model';
import { UserManagementService } from 'src/app/modules/user-management/user-management.service';

@Component({
  selector: 'app-profile-details',
  templateUrl: './profile-details.component.html',
})
export class ProfileDetailsComponent implements OnInit, OnDestroy, OnChanges {
  private unsubscribe: Subscription[] = [];
  form: FormGroup;

  @Input() user: UserModel;
  constructor(private fb: FormBuilder, private userManagementService: UserManagementService,
    private alertService: AlertService
  ) {

  }
  
  ngOnChanges(changes: SimpleChanges): void {
    if(changes.user) {
      if(!this.form) {
        this.initForm();
      }
      
      this.setUserForm();
    }
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
      surname: [
        "",
        Validators.compose([
          Validators.required,
        ]),
      ],
      email: [
        "",
        Validators.compose([
          Validators.required,
          Validators.email,
          Validators.minLength(3),
          Validators.maxLength(320),
        ]),
      ],
      phone: [
        "",
        Validators.compose([
          Validators.required,
        ]),
      ],
      roles: [
        null
      ],
      organizations: [
        null
      ],
      username: [
        "",
        Validators.compose([
          Validators.required,
        ]),
      ],
      password: [
        '',
      ],
      fileId: [
        '',
      ],
    });
  }

  setUserForm() {
    
    if (this.user) {
      this.form.patchValue(this.user);

      this.form.get("password")?.setValue("***");
      this.form.get("cPassword")?.setValue("***");
      this.form.get("roles")?.setValue(this.user.roles[0])

      if (this.user.organizations.length > 0) {
        this.form.get("organizations")?.setValue(this.user.organizations[0])
      }
      else {
        this.form.get("organizations")?.setValue(null)
      }
    }
}

ngOnInit(): void {
  this.initForm();
}

saveSettings() {
  if (this.form.valid) {
    var temp = this.form.getRawValue();
    var data = this.form.getRawValue() as UserModel;

    if (temp.roles || temp.roles > 0) {
      data.roles = [temp.roles];
    }
    else {
      data.roles = [];
    }

    if (temp.organizations || temp.organizations > 0) {
      data.organizations = [temp.organizations];
    }
    else {
      data.organizations = [];
    }

    this.userManagementService.userProfileEdit(data).subscribe(result => {
      if (result.isSuccess) {
        this.alertService.createAlert("success", result.message);
        this.userManagementService.updateUser(data.id);
      }
      else {
        this.alertService.createAlert("danger", result.message);
      }
    })
  }
}

ngOnDestroy() {
  this.unsubscribe.forEach((sb) => sb.unsubscribe());
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

      if (width == 300 && height == 300) {
        let formData = new FormData();
        formData.append("file", file);

        this.userManagementService.upload(formData).subscribe(result => {
          if (result.isSuccess) {
            this.userManagementService.userAvatarEdit(this.user.id, result.data.id).subscribe(result => {
              if (result.isSuccess) {
                this.alertService.createAlert("success", result.message);
                this.userManagementService.updateUser(this.user.id);
              }
              else {
                this.alertService.createAlert("danger", result.message);
              }
            })
          }
          else {
            this.alertService.createAlert("danger", result.message);
          }
        })
      }
      else {
        this.alertService.createAlert("warning", "Lütfen, 300x300 boyutlarında bir resim dosyası yükleyiniz!");
      }
    };
  }
}

}
